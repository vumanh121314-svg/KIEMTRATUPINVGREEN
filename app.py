import math
from xml.etree import ElementTree as ET
import folium
from folium.plugins import LocateControl
import streamlit as st
from streamlit_folium import st_folium

st.set_page_config(
    page_title="Tìm Tủ Pin V-GREEN Gần Nhất",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🔋 Tìm Đường Ngắn Nhất Đến Tủ Pin V-GREEN")
st.markdown(
    "Ứng dụng tự động quét các file bản đồ KML, xác định **vị trí hiện tại** của"
    " bạn và tính khoảng cách đường đi ngắn nhất đến tủ pin gần nhất."
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


# Đọc dữ liệu từ file KML
def load_stations_from_kml(file_obj):
  stations_list = []
  try:
    tree = ET.parse(file_obj)
    root = tree.getroot()
    namespaces = {"kml": "http://www.opengis.net/kml/2.2"}
    for placemark in root.findall(".//kml:Placemark", namespaces):
      name_elem = placemark.find("kml:name", namespaces)
      coord_elem = placemark.find(".//kml:coordinates", namespaces)
      if name_elem is not None and coord_elem is not None:
        coords_text = coord_elem.text.strip().split()[
            0
        ]  # Lấy tọa độ đầu tiên
        parts = coords_text.split(",")
        if len(parts) >= 2:
          lon = float(parts[0])
          lat = float(parts[1])
          stations_list.append(
              {"name": name_elem.text.strip(), "lat": lat, "lon": lon}
          )
  except Exception as e:
    st.error(f"Lỗi đọc file: {e}")
  return stations_list


# Sidebar tải file KML hoặc KMZ (lưu ý: giải nén file KMZ lấy file doc.kml tải lên)
st.sidebar.header("📁 Tải lên dữ liệu bản đồ")
uploaded_files = st.sidebar.file_uploader(
    "Chọn các file .kml (hoặc doc.kml từ file KMZ)",
    type=["kml"],
    accept_multiple_files=True,
)

all_stations = []
if uploaded_files:
  for uploaded_file in uploaded_files:
    st_list = load_stations_from_kml(uploaded_file)
    all_stations.extend(st_list)
  st.sidebar.success(f"Đã nạp tổng cộng {len(all_stations)} điểm tủ pin!")
else:
  st.sidebar.info(
      "💡 Hãy tải các file `doc.kml` được trích xuất từ các file KMZ bản đồ của"
      " bạn lên đây."
  )

# Tọa độ mặc định (Khu vực Đồng Nai / Bình Phước)
default_lat, default_lon = 11.50567, 106.88714

if "current_loc" not in st.session_state:
  st.session_state["current_loc"] = (default_lat, default_lon)

# Khởi tạo bản đồ
m = folium.Map(
    location=st.session_state["current_loc"], zoom_start=13, tiles="OpenStreetMap"
)

# Thêm tính năng định vị GPS thực tế của trình duyệt (Geolocate)
LocateControl(
    auto_start=False,
    position="topleft",
    strings={"title": "Định vị vị trí của tôi", "popup": "Bạn đang ở đây"},
).add_to(m)

# Vẽ các tủ pin lên bản đồ
for stn in all_stations:
  folium.Marker(
      location=[stn["lat"], stn["lon"]],
      popup=stn["name"],
      icon=folium.Icon(color="green", icon="motorcycle", prefix="fa"),
  ).add_to(m)

# Đánh dấu vị trí hiện tại (click trên bản đồ hoặc GPS)
curr_lat, curr_lon = st.session_state["current_loc"]
folium.Marker(
    location=[curr_lat, curr_lon],
    popup="Vị trí hiện tại của bạn",
    icon=folium.Icon(color="red", icon="user", prefix="fa"),
).add_to(m)

# Tìm tủ pin gần nhất và vẽ đường nối
nearest_station = None
min_dist = float("inf")

if all_stations:
  for stn in all_stations:
    dist = haversine(curr_lat, curr_lon, stn["lat"], stn["lon"])
    if dist < min_dist:
      min_dist = dist
      nearest_station = stn

  if nearest_station:
    folium.PolyLine(
        locations=[
            [curr_lat, curr_lon],
            [nearest_station["lat"], nearest_station["lon"]],
        ],
        color="blue",
        weight=4,
        opacity=0.8,
        tooltip=(
            f"Khoảng cách tới {nearest_station['name']}: {min_dist:.2f} km"
        ),
    ).add_to(m)

# Giao diện hiển thị
col1, col2 = st.columns([2, 1])

with col1:
  st.subheader("🗺️ Bản đồ tương tác")
  st.markdown(
      "*(Bấm vào nút định vị ở góc trái bản đồ hoặc click trực tiếp lên bản"
      " đồ để chọn vị trí đứng của bạn)*"
  )
  output = st_folium(m, width="100%", height=550)

  # Cập nhật vị trí khi người dùng click
  if output and output.get("last_clicked"):
    clicked_lat = output["last_clicked"]["lat"]
    clicked_lon = output["last_clicked"]["lng"]
    if (
        clicked_lat != st.session_state["current_loc"][0]
        or clicked_lon != st.session_state["current_loc"][1]
    ):
      st.session_state["current_loc"] = (clicked_lat, clicked_lon)
      st.rerun()

with col2:
  st.subheader("📊 Kết quả khoảng cách")
  if nearest_station:
    st.success(f"**Tủ pin gần nhất:**\n\n🔹 **{nearest_station['name']}**")
    st.metric(label="Khoảng cách đường chim bay", value=f"{min_dist:.2f} km")
    st.write(f"📍 **Tọa độ tủ:** `{nearest_station['lat']}, {nearest_station['lon']}`")
    st.write(f"📍 **Vị trí của bạn:** `{curr_lat:.5f}, {curr_lon:.5f}`")

    maps_url = (
        f"https://www.google.com/maps/dir/?api=1&destination="
        f"{nearest_station['lat']},{nearest_station['lon']}"
    )
    st.markdown(
        f"[👉 Mở chỉ đường chi tiết trên Google Maps]({maps_url})",
        unsafe_allow_html=True,
    )
  else:
    st.warning(
        "Vui lòng tải các file bản đồ (.kml) lên từ thanh menu bên trái để bắt"
        " đầu tìm kiếm."
    )
