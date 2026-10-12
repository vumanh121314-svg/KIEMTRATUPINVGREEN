import io
import math
import zipfile
from xml.etree import ElementTree as ET
import folium
import streamlit as st
from streamlit_folium import st_folium

st.set_page_config(
    page_title="Tìm Tủ Pin V-GREEN Từ File KMZ",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🔋 Tìm Đường Ngắn Nhất Đến Tủ Pin V-GREEN (Hỗ trợ file KMZ)")
st.markdown(
    "Tải lên các file `.kmz` của bạn, nhập vị trí cần tìm kiếm để hệ thống so"
    " sánh và tìm ra tủ pin gần nhất."
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


# Hàm trích xuất dữ liệu từ file KMZ hoặc KML
def load_stations_from_kmz_or_kml(uploaded_file):
  stations_list = []
  try:
    file_bytes = uploaded_file.read()
    kml_content = None

    # Kiểm tra nếu là file .kmz (bản chất là file zip)
    if uploaded_file.name.endswith(".kmz") or zipfile.is_zipfile(
        io.BytesIO(file_bytes)
    ):
      with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
        # Tìm file kml bên trong file kmz (thường là doc.kml)
        for filename in z.namelist():
          if filename.endswith(".kml"):
            with z.open(filename) as kml_file:
              kml_content = kml_file.read()
            break
    else:
      # Nếu là file .kml thông thường
      kml_content = file_bytes

    if kml_content:
      root = ET.fromstring(kml_content)
      namespaces = {"kml": "http://www.opengis.net/kml/2.2"}
      for placemark in root.findall(".//kml:Placemark", namespaces):
        name_elem = placemark.find("kml:name", namespaces)
        coord_elem = placemark.find(".//kml:coordinates", namespaces)
        if name_elem is not None and coord_elem is not None:
          coords_text = coord_elem.text.strip().split()[0]
          parts = coords_text.split(",")
          if len(parts) >= 2:
            stations_list.append({
                "name": name_elem.text.strip(),
                "lat": float(parts[1]),
                "lon": float(parts[0]),
            })
  except Exception as e:
    st.sidebar.error(f"Lỗi đọc file {uploaded_file.name}: {e}")
  return stations_list


# --- THANH BÊN: TẢI LÊN CÁC FILE KMZ ---
st.sidebar.header("📁 Tải lên file bản đồ KMZ")
uploaded_files = st.sidebar.file_uploader(
    "Chọn các file .kmz của bạn (có thể chọn nhiều file cùng lúc)",
    type=["kmz", "kml"],
    accept_multiple_files=True,
)

all_stations = []
if uploaded_files:
  for uploaded_file in uploaded_files:
    st_list = load_stations_from_kmz_or_kml(uploaded_file)
    all_stations.extend(st_list)
  st.sidebar.success(f"Đã nạp tổng cộng {len(all_stations)} điểm tủ pin từ file!")
else:
  st.sidebar.info(
      "💡 Vui lòng tải các file bản đồ `.kmz` lên đây để hệ thống nạp dữ liệu."
  )

# --- KHU VỰC NHẬP VỊ TRÍ CẦN TÌM KIẾM ---
st.sidebar.markdown("---")
st.sidebar.header("🎯 Nhập vị trí cần tìm kiếm")
input_mode = st.sidebar.radio(
    "Chọn phương thức nhập:", ("Nhập tọa độ thủ công", "Click trực tiếp trên bản đồ")
)

# Tọa độ mặc định ban đầu
default_lat, default_lon = 11.50567, 106.88714

if "search_loc" not in st.session_state:
  st.session_state["search_loc"] = (default_lat, default_lon)

if input_mode == "Nhập tọa độ thủ công":
  col_lat, col_lon = st.sidebar.columns(2)
  with col_lat:
    entered_lat = st.number_input(
        "Vĩ độ (Lat)", value=st.session_state["search_loc"][0], format="%.6f"
    )
  with col_lon:
    entered_lon = st.number_input(
        "Kinh độ (Lon)", value=st.session_state["search_loc"][1], format="%.6f"
    )
  st.session_state["search_loc"] = (entered_lat, entered_lon)

# Khởi tạo bản đồ
m = folium.Map(
    location=st.session_state["search_loc"], zoom_start=13, tiles="OpenStreetMap"
)

# Đánh dấu các tủ pin từ file KMZ
for stn in all_stations:
  folium.Marker(
      location=[stn["lat"], stn["lon"]],
      popup=stn["name"],
      icon=folium.Icon(color="green", icon="motorcycle", prefix="fa"),
  ).add_to(m)

# Đánh dấu vị trí cần tìm kiếm
target_lat, target_lon = st.session_state["search_loc"]
folium.Marker(
    location=[target_lat, target_lon],
    popup="Vị trí bạn đang tìm kiếm",
    icon=folium.Icon(color="orange", icon="crosshairs", prefix="fa"),
).add_to(m)

# Tính toán tìm tủ pin gần nhất
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

# Giao diện chính chia 2 cột
col1, col2 = st.columns([2, 1])

with col1:
  st.subheader("🗺️ Bản đồ đối chiếu")
  if input_mode == "Click trực tiếp trên bản đồ":
    st.markdown("*(Click vào bất kỳ điểm nào trên bản đồ để chọn vị trí)*")
  output = st_folium(m, width="100%", height=550)

  if (
      input_mode == "Click trực tiếp trên bản đồ"
      and output
      and output.get("last_clicked")
  ):
    clicked_lat = output["last_clicked"]["lat"]
    clicked_lon = output["last_clicked"]["lng"]
    if (
        clicked_lat != st.session_state["search_loc"][0]
        or clicked_lon != st.session_state["search_loc"][1]
    ):
      st.session_state["search_loc"] = (clicked_lat, clicked_lon)
      st.rerun()

with col2:
  st.subheader("📊 Kết quả so sánh khoảng cách")
  if nearest_station:
    st.success(
        f"**Tủ pin gần vị trí nhập nhất:**\n\n🔹 **{nearest_station['name']}**"
    )
    st.metric(
        label="Khoảng cách đường chim bay", value=f"{min_dist:.2f} km"
    )
    st.write(
        f"📍 **Tọa độ tủ trên file:** `{nearest_station['lat']}, {nearest_station['lon']}`"
    )
    st.write(f"📍 **Vị trí bạn tìm kiếm:** `{target_lat:.5f}, {target_lon:.5f}`")

    maps_url = (
        f"https://www.google.com/maps/dir/?api=1&destination="
        f"{nearest_station['lat']},{nearest_station['lon']}"
    )
    st.markdown(
        f"[👉 Mở chỉ đường chi tiết trên Google Maps]({maps_url})",
        unsafe_allow_html=True,
    )
  else:
    st.warning("Vui lòng tải các file bản đồ `.kmz` lên ở thanh bên trái.")
