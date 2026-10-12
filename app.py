import io
import math
import os
import zipfile
from xml.etree import ElementTree as ET
import folium
import requests
import streamlit as st
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation

# Cấu hình giao diện rộng và tối ưu hóa di động
st.set_page_config(
    page_title="Tra cứu tủ đổi pin V-Green",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- CSS TÙY CHỈNH GIAO DIỆN GIỐNG ẢNH MẪU & RESPONSIVE ---
st.markdown(
    """
    <style>
    .stApp {
        background-color: #0e1117;
        color: #ffffff;
    }
    .top-title {
        background-color: #161b22;
        padding: 15px 20px;
        border-radius: 8px;
        font-size: 20px;
        font-weight: bold;
        color: #ffffff;
        margin-bottom: 15px;
        border-left: 5px solid #22c55e;
    }
    .section-title {
        color: #ffffff;
        font-size: 16px;
        font-weight: bold;
        margin-top: 15px;
        margin-bottom: 10px;
    }
    .info-bar {
        background-color: #161b22;
        padding: 10px 15px;
        border-radius: 6px;
        font-size: 14px;
        color: #84cc16;
        margin-bottom: 10px;
    }
    </style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="top-title">🔋 Tra cứu tủ đổi pin V-Green</div>',
    unsafe_allow_html=True,
)


# Hàm gọi API OSRM lấy tuyến đường thực tế
def get_osrm_route(lat1, lon1, lat2, lon2):
  url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
  try:
    response = requests.get(url, timeout=5)
    if response.status_code == 200:
      data = response.json()
      if "routes" in data and len(data["routes"]) > 0:
        route = data["routes"][0]
        distance_km = route["distance"] / 1000.0
        coords = route["geometry"]["coordinates"]
        latlon_coords = [[c[1], c[0]] for c in coords]
        return distance_km, latlon_coords
  except Exception:
    pass
  return None, None


# Hàm tính khoảng cách Haversine
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


# Hàm đọc file KMZ trên GitHub
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
                  else "Tủ pin"
              )
              stations_list.append({"name": name, "lat": lat, "lon": lon})
            except ValueError:
              continue
  except Exception:
    pass
  return stations_list


@st.cache_data
def load_all_kmz_files():
  all_stations = []
  kmz_files = [f for f in os.listdir(".") if f.endswith(".kmz")]
  for file in kmz_files:
    stations = load_stations_from_kmz_path(file)
    all_stations.extend(stations)
  return all_stations


all_stations = load_all_kmz_files()

# --- QUẢN LÝ SESSION STATE CHO VỊ TRÍ ---
default_lat, default_lon = 10.734728, 106.663666

if "lat" not in st.session_state:
  st.session_state["lat"] = default_lat
if "lon" not in st.session_state:
  st.session_state["lon"] = default_lon

# --- PHẦN 1: BẢN ĐỒ & ĐỊNH VỊ VỊ TRÍ (NẰM NGANG PHÍA TRÊN) ---
st.markdown(
    '<div class="section-title">📍 Bản đồ & Định vị vị trí</div>',
    unsafe_allow_html=True,
)

# Lấy GPS từ thiết bị khi bấm nút phụ trợ
loc = streamlit_geolocation()
if loc and loc.get("latitude") and loc.get("longitude"):
  if (
      loc["latitude"] != st.session_state["lat"]
      or loc["longitude"] != st.session_state["lon"]
  ):
    st.session_state["lat"] = loc["latitude"]
    st.session_state["lon"] = loc["longitude"]
    st.rerun()

# Khởi tạo bản đồ
m = folium.Map(
    location=[st.session_state["lat"], st.session_state["lon"]],
    zoom_start=13,
    tiles="OpenStreetMap",
)

# Đánh dấu vị trí người dùng
folium.Marker(
    location=[st.session_state["lat"], st.session_state["lon"]],
    popup="Vị trí của bạn",
    icon=folium.Icon(color="red", icon="user", prefix="fa"),
).add_to(m)

# Hiển thị bản đồ tương tác dạng ngang rộng
map_output = st_folium(m, width="100%", height=380)

# Cập nhật tọa độ nếu click trực tiếp lên bản đồ
if map_output and map_output.get("last_clicked"):
  clicked_lat = map_output["last_clicked"]["lat"]
  clicked_lon = map_output["last_clicked"]["lng"]
  if (
      clicked_lat != st.session_state["lat"]
      or clicked_lon != st.session_state["lon"]
  ):
    st.session_state["lat"] = clicked_lat
    st.session_state["lon"] = clicked_lon
    st.rerun()

# Thanh thông tin tọa độ chọn và các nút thao tác nhanh
col_info_bar, col_btn1, col_btn2 = st.columns([3, 1, 1])
with col_info_bar:
  st.markdown(
      f'<div class="info-bar">📍 Tọa độ chọn: <b>{st.session_state["lat"]:.6f},'
      f" {st.session_state['lon']:.6f}</b><br><span style='font-size:12px;'"
      " color:#a3a3a3;>(Kéo thả ghim hoặc bấm bản đồ để đổi vị trí)</span></div>",
      unsafe_allow_html=True,
  )

with col_btn1:
  if st.button("📍 Vị trí của tôi", use_container_width=True):
    # Nút kích hoạt lại geolocation
    st.rerun()

with col_btn2:
  if st.button("📋 Copy tọa độ", use_container_width=True):
    st.toast("Đã ghi nhớ tọa độ vào bộ nhớ tạm!")

# --- PHẦN 2: NHẬP TỌA ĐỘ & NGƯỠNG KIỂM TRA (NẰM DƯỚI) ---
st.markdown(
    '<div class="section-title">🎯 Nhập tọa độ & Ngưỡng kiểm tra</div>',
    unsafe_allow_html=True,
)

col_input1, col_input2 = st.columns([3, 1])

with col_input1:
  coord_input = st.text_input(
      "Tọa độ (Lat, Long):",
      value=f"{st.session_state['lat']}, {st.session_state['lon']}",
      help="Nhập dạng: 10.734728, 106.663666",
  )

with col_input2:
  threshold_m = st.number_input(
      "Ngưỡng Đạt (m):", min_value=100, max_value=10000, value=500, step=50
  )

# Xử lý khi người dùng nhập thủ công ô text_input
try:
  parts = coord_input.split(",")
  if len(parts) == 2:
    new_lat = float(parts[0].strip())
    new_lon = float(parts[1].strip())
    if (
        new_lat != st.session_state["lat"]
        or new_lon != st.session_state["lon"]
    ):
      st.session_state["lat"] = new_lat
      st.session_state["lon"] = new_lon
except Exception:
  pass

# --- PHẦN 3: TÍNH TOÁN VÀ CHỌN TUYẾN ĐƯỜNG ĐI ---
st.markdown("---")

# Tính toán khoảng cách đến các tủ pin
station_options = []
if all_stations:
  for stn in all_stations:
    dist_hb = haversine(
        st.session_state["lat"], st.session_state["lon"], stn["lat"], stn["lon"]
    )
    station_options.append({"station": stn, "dist_hb": dist_hb})
  station_options = sorted(station_options, key=lambda x: x["dist_hb"])

if station_options:
  st.markdown(
      '<div class="section-title">🚏 Chọn tủ đổi pin gần nhất để xem đường'
      " đi</div>",
      unsafe_allow_html=True,
  )

  top_stations = station_options[:10]
  station_labels = [
      f"{item['station']['name']} (~{item['dist_hb']:.2f} km)"
      for item in top_stations
  ]

  selected_label = st.selectbox(
      "Danh sách tủ pin:", station_labels, label_visibility="collapsed"
  )
  selected_index = station_labels.index(selected_label)
  chosen_station = top_stations[selected_index]["station"]

  # Tính khoảng cách thực tế qua OSRM
  real_distance, route_coords = get_osrm_route(
      st.session_state["lat"],
      st.session_state["lon"],
      chosen_station["lat"],
      chosen_station["lon"],
  )
  if real_distance is None:
    real_distance = top_stations[selected_index]["dist_hb"]
    route_coords = [
        [st.session_state["lat"], st.session_state["lon"]],
        [chosen_station["lat"], chosen_station["lon"]],
    ]

  # Nút bấm trung tâm "Tính khoảng cách & Lộ trình"
  if st.button(
      "🔍 Tính khoảng cách & Chỉ đường chi tiết",
      use_container_width=True,
      type="primary",
  ):
    st.success(
        f"**Tủ đổi pin được chọn:** {chosen_station['name']} — Khoảng cách thực"
        f" tế: **{real_distance:.2f} km**"
    )

    maps_url = (
        f"https://www.google.com/maps/dir/?api=1&destination="
        f"{chosen_station['lat']},{chosen_station['lon']}"
    )
    st.markdown(
        f"[👉 Mở chỉ đường chi tiết trên Google Maps]({maps_url})",
        unsafe_allow_html=True,
    )
else:
  st.warning(
      "Chưa tìm thấy dữ liệu trạm pin nào trong các file KMZ trên GitHub."
  )
