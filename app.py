import io
import math
import os
import zipfile
from xml.etree import ElementTree as ET
import folium
import streamlit as st
from streamlit_folium import st_folium

st.set_page_config(
    page_title="Tìm Điểm Gần Nhất Từ File KMZ Sẵn Có",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🔋 Tìm Đường Ngắn Nhất Tới Trạm / Tủ Pin Từ Các File KMZ Trên GitHub")
st.markdown(
    "Hệ thống đang tự động đọc các file `.kmz` có sẵn trong dự án. Bạn chỉ cần"
    " nhập tọa độ vị trí cần kiểm tra ở thanh bên trái."
)


# Hàm tính khoảng cách Haversine (km)
def haversine(lat1, lon1, lat2, lon2):
  R = 6371.0
  dlat = math.radians(lat2 - lat1)
  dlon = math.radians(lon2 - lon1)
  a = (
      math.sin(dlat / 2) ** 2
      + math.cos(math.radians(lat1))
      * math.cos(math.radians(lat2))
      * math.sin(dlon / 2) ** 2
  )
  c = 2 * math.asin(math.sqrt(a))
  return R * c


# Hàm trích xuất dữ liệu từ tệp KMZ
def load_stations_from_kmz_path(file_path):
  stations_list = []
  try:
    with open(file_path, "rb") as f:
      file_bytes = f.read()

    kml_content = None
    if zipfile.is_zipfile(io.BytesIO(file_bytes)):
      with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
        for filename in z.namelist():
          if filename.endswith(".kml"):
            with z.open(filename) as kml_file:
              kml_content = kml_file.read()
            break
    else:
      kml_content = file_bytes

    if kml_content:
      root = ET.fromstring(kml_content)
      namespaces = {"kml": "http://www.opengis.net/kml/2.2"}
      for placemark in root.findall(".//kml:Placemark", namespaces):
        name_elem = placemark.find("kml:name", namespaces)
        coord_elem = placemark.find(".//kml:coordinates", namespaces)

        if (
            coord_elem is not None
            and coord_elem.text
            and coord_elem.text.strip()
        ):
          coords_text = coord_elem.text.strip().split()[0]
          parts = coords_text.split(",")
          if len(parts) >= 2:
            try:
              lon = float(parts[0])
              lat = float(parts[1])
              name = (
                  name_elem.text.strip()
                  if name_elem is not None and name_elem.text
                  else "Điểm không tên"
              )
              stations_list.append({"name": name, "lat": lat, "lon": lon})
            except ValueError:
              continue
  except Exception as e:
    st.error(f"Lỗi khi đọc file {file_path}: {e}")
  return stations_list


# Tự động quét tất cả các file có đuôi .kmz trong thư mục hiện tại của GitHub
@st.cache_data
def load_all_kmz_files():
  all_stations = []
  kmz_files = [f for f in os.listdir(".") if f.endswith(".kmz")]

  for file in kmz_files:
    stations = load_stations_from_kmz_path(file)
    all_stations.extend(stations)

  return all_stations, kmz_files


# Nạp dữ liệu tự động
with st.spinner("Đang trích xuất dữ liệu từ các file .kmz có sẵn..."):
  all_stations, found_files = load_all_kmz_files()

st.sidebar.success(
    f"Đã quét thấy {len(found_files)} file .kmz và nạp tổng cộng"
    f" {len(all_stations)} điểm!"
)


# --- NHẬP VỊ TRÍ CẦN TÌM KIẾM ---
st.sidebar.markdown("---")
st.sidebar.header("🎯 Nhập tọa độ vị trí của bạn")

# Giá trị mặc định (Lấy trung tâm Đồng Nai / Bình Phước)
default_lat, default_lon = 11.50567, 106.88714

entered_lat = st.sidebar.number_input(
    "Vĩ độ (Lat)", value=default_lat, format="%.6f"
)
entered_lon = st.sidebar.number_input(
    "Kinh độ (Lon)", value=default_lon, format="%.6f"
)

target_lat, target_lon = entered_lat, entered_lon

# Khởi tạo bản đồ tại vị trí vừa nhập
m = folium.Map(location=[target_lat, target_lon], zoom_start=11, tiles="OpenStreetMap")

# Đánh dấu các điểm tủ pin trên bản đồ
for stn in all_stations:
  folium.Marker(
      location=[stn["lat"], stn["lon"]],
      popup=stn["name"],
      icon=folium.Icon(color="green", icon="motorcycle", prefix="fa"),
  ).add_to(m)

# Đánh dấu vị trí đang tìm kiếm
folium.Marker(
    location=[target_lat, target_lon],
    popup="Vị trí bạn đang đứng",
    icon=folium.Icon(color="orange", icon="crosshairs", prefix="fa"),
).add_to(m)

# Tính toán tìm điểm gần nhất
nearest_station = None
min_dist = float("inf")

if all_stations:
  for stn in all_stations:
    dist = haversine(target_lat, target_lon, stn["lat"], stn["lon"])
    if dist < min_dist:
      min_dist = dist
      nearest_station = stn

  if nearest_station:
    folium.PolyLine(
        locations=[
            [target_lat, target_lon],
            [nearest_station["lat"], nearest_station["lon"]],
        ],
        color="red",
        weight=4,
        opacity=0.8,
        tooltip=(
            f"Khoảng cách đến {nearest_station['name']}: {min_dist:.2f} km"
        ),
    ).add_to(m)

# Giao diện hiển thị trực quan
col_map, col_info = st.columns([2, 1])

with col_map:
  st.subheader("🗺️ Bản đồ đối chiếu trực quan")
  st_folium(m, width="100%", height=550)

with col_info:
  st.subheader("📊 Kết quả khoảng cách")
  if nearest_station:
    st.success(
        f"**Điểm gần vị trí nhập nhất:**\n\n🔹 **{nearest_station['name']}**"
    )
    st.metric(
        label="Khoảng cách đường chim bay", value=f"{min_dist:.2f} km"
    )
    st.write(
        f"📍 **Tọa độ điểm trên file KMZ:** `{nearest_station['lat']}, {nearest_station['lon']}`"
    )
    st.write(f"📍 **Vị trí bạn nhập:** `{target_lat:.5f}, {target_lon:.5f}`")

    maps_url = (
        f"https://www.google.com/maps/dir/?api=1&destination="
        f"{nearest_station['lat']},{nearest_station['lon']}"
    )
    st.markdown(
        f"[👉 Mở chỉ đường chi tiết trên Google Maps]({maps_url})",
        unsafe_allow_html=True,
    )
  else:
    st.warning("Không tìm thấy điểm dữ liệu nào từ các file .kmz đã tải lên.")
