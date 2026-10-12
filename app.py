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

# Cấu hình giao diện rộng và tương thích trên mọi thiết bị
st.set_page_config(
    page_title="Tra cứu tủ đổi pin V-Green",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- CSS TÙY CHỈNH GIAO DIỆN & RESPONSIVE ---
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
    .result-card {
        background-color: #161b22;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #22c55e;
        margin-top: 15px;
    }
    </style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="top-title">🔋 Tra cứu tủ đổi pin V-Green</div>',
    unsafe_allow_html=True,
)


# Hàm gọi API OSRM lấy tuyến đường thực tế và khoảng cách đường bộ
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

# --- QUẢN LÝ SESSION STATE ---
default_lat, default_lon = 10.734728, 106.663666

if "lat" not in st.session_state:
  st.session_state["lat"] = default_lat
if "lon" not in st.session_state:
  st.session_state["lon"] = default_lon
if "selected_station" not in st.session_state:
  st.session_state["selected_station"] = None

# --- PHẦN 1: BẢN ĐỒ & ĐỊNH VỊ VỊ TRÍ ---
st.markdown(
    '<div class="section-title">📍 Bản đồ & Định vị vị trí</div>',
    unsafe_allow_html=True,
)

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

# Tìm tủ pin gần nhất mặc định để chọn sẵn nếu chưa chọn
nearest_default = None
min_d = float("inf")
if all_stations:
  for stn in all_stations:
    d = haversine(
        st.session_state["lat"],
        st.session_state["lon"],
        stn["lat"],
        stn["lon"],
    )
    if d < min_d:
      min_d = d
      nearest_default = stn

  if not st.session_state["selected_station"] and nearest_default:
    st.session_state["selected_station"] = nearest_default

# Đánh dấu các tủ pin lên bản đồ (Icon màu xanh lá)
for stn in all_stations:
  is_selected = (
      st.session_state["selected_station"]
      and st.session_state["selected_station"]["name"] == stn["name"]
      and st.session_state["selected_station"]["lat"] == stn["lat"]
  )
  icon_color = "orange" if is_selected else "green"
  icon_type = "bolt" if is_selected else "battery-full"

  folium.Marker(
      location=[stn["lat"], stn["lon"]],
      popup=stn["name"],
      icon=folium.Icon(color=icon_color, icon=icon_type, prefix="fa"),
  ).add_to(m)

# Nếu đã chọn tủ pin, vẽ đường đi thực tế trên bản đồ
route_coords = []
real_distance = 0
if st.session_state["selected_station"]:
  sel = st.session_state["selected_station"]
  real_distance, route_coords = get_osrm_route(
      st.session_state["lat"], st.session_state["lon"], sel["lat"], sel["lon"]
  )
  if real_distance is None:
    real_distance = haversine(
        st.session_state["lat"], st.session_state["lon"], sel["lat"], sel["lon"]
    )
    route_coords = [
        [st.session_state["lat"], st.session_state["lon"]],
        [sel["lat"], sel["lon"]],
    ]

  if route_coords:
    folium.PolyLine(
        locations=route_coords,
        color="blue",
        weight=5,
        opacity=0.8,
        tooltip=f"Lộ trình tới {sel['name']}",
    ).add_to(m)

# Hiển thị bản đồ
map_output = st_folium(m, width="100%", height=380)

# Xử lý khi click vào bản đồ để đổi vị trí hiện tại
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

#
