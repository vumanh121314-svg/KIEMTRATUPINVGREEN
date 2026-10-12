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

# Cấu hình giao diện tương thích tốt trên thiết bị di động và máy tính
st.set_page_config(
    page_title="Tìm Trạm Pin Gần Nhất & Chỉ Đường",
    layout="wide",
    initial_sidebar_state="auto",
)

st.title("🔋 Tìm Đường Đi Thực Tế Tới Trạm Pin V-GREEN")
st.markdown(
    "Ứng dụng tự động quét các file `.kmz` trên GitHub, tính toán khoảng cách và"
    " vẽ lộ trình đường bộ chính xác từ vị trí của bạn."
)


# Hàm gọi API OSRM để lấy khoảng cách đường đi thực tế và tọa độ vẽ đường
def get_osrm_route(lat1, lon1, lat2, lon2):
  url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
  try:
    response = requests.get(url, timeout=5)
    if response.status_code == 200:
      data = response.json()
      if "routes" in data and len(data["routes"]) > 0:
        route = data["routes"][0]
        distance_km = route["distance"] / 1000.0  # Đổi ra km
        duration_min = route["duration"] / 60.0  # Đổi ra phút
        coords = route["geometry"]["coordinates"]  # Danh sách [lon, lat]
        latlon_coords = [[c[1], c[0]] for c in coords]  # Đổi thành [lat, lon]
        return distance_km, duration_min, latlon_coords
  except Exception:
    pass
  return None, None, None


# Hàm tính khoảng cách phụ trợ (Haversine) để lọc nhanh nếu cần
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


# Hàm trích xuất dữ liệu từ tệp KMZ có sẵn trên GitHub
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


# Tự động quét tất cả file .kmz trong thư mục
@st.cache_data
def load_all_kmz_files():
  all_stations = []
  kmz_files = [f for f in os.listdir(".") if f.endswith(".kmz")]
  for file in kmz_files:
    stations = load_stations_from_kmz_path(file)
    all_stations.extend(stations)
  return all_stations, kmz_files


with st.spinner("Đang quét dữ liệu trạm từ GitHub..."):
  all_stations, found_files = load_all_kmz_files()

st.sidebar.success(
    f"Đã nạp {len(all_stations)} điểm từ {len(found_files)} file .kmz!"
)

# --- KHU VỰC ĐỊNH VỊ & NHẬP TỌA ĐỘ ---
st.sidebar.markdown("---")
st.sidebar.header("🎯 Vị trí của bạn")

# Nút lấy vị trí GPS từ thiết bị (Điện thoại/Máy tính)
st.sidebar.subheader("Cách 1: Lấy GPS tự động")
loc = streamlit_geolocation()

default_lat, default_lon = 11.50567, 106.88714

if loc and loc.get("latitude") and loc.get("longitude"):
  current_lat = loc["latitude"]
  current_lon = loc["longitude"]
  st.sidebar.success("Đã lấy vị trí thiết bị thành công!")
else:
  current_lat, current_lon = default_lat, default_lon

st.sidebar.markdown("---")
st.sidebar.subheader("Cách 2: Nhập tọa độ thủ công")
entered_lat = st.sidebar.number_input(
    "Vĩ độ (Lat)", value=float(current_lat), format="%.6f"
)
entered_lon = st.sidebar.number_input(
    "Kinh độ (Lon)", value=float(current_lon), format="%.6f"
)

target_lat, target_lon = entered_lat, entered_lon

# Tìm điểm gần nhất bằng đường chim bay trước để tối ưu, sau đó tính đường đi thực tế
nearest_station = None
min_dist = float("inf")
route_coords = []
real_distance = 0
travel_duration = 0

if all_stations:
  # Lọc sơ bộ lấy 5 điểm gần nhất bằng Haversine để tiết kiệm thời gian gọi API đường đi
  sorted_stations = sorted(
      all_stations,
      key=lambda s: haversine(target_lat, target_lon, s["lat"], s["lon"]),
  )

  # Xét top các điểm gần nhất để tìm ra đường đi bộ/xe ngắn thực tế
  for stn in sorted_stations[:10]:
    dist_hb = haversine(target_lat, target_lon, stn["lat"], stn["lon"])
    if dist_hb < min_dist + 20:  # Biên độ lọc
      d_road, dur, coords = get_osrm_route(
          target_lat, target_lon, stn["lat"], stn["lon"]
      )
      if d_road is not None and d_road < min_dist:
        min_dist = d_road
        nearest_station = stn
        travel_duration = dur
        route_coords = coords

  # Fallback nếu không gọi được API đường đi
  if not nearest_station and sorted_stations:
    nearest_station = sorted_stations[0]
    real_distance = haversine(
        target_lat, target_lon, nearest_station["lat"], nearest_station["lon"]
    )
    route_coords = [
        [target_lat, target_lon],
        [nearest_station["lat"], nearest_station["lon"]],
    ]
  else:
    real_distance = min_dist

# Khởi tạo bản đồ Folium
m = folium.Map(location=[target_lat, target_lon], zoom_start=13, tiles="OpenStreetMap")

# Đánh dấu các trạm pin
for stn in all_stations:
  folium.Marker(
      location=[stn["lat"], stn["lon"]],
      popup=stn["name"],
      icon=folium.Icon(color="green", icon="motorcycle", prefix="fa"),
  ).add_to(m)

# Đánh dấu vị trí hiện tại của bạn
folium.Marker(
    location=[target_lat, target_lon],
    popup="Vị trí của bạn",
    icon=folium.Icon(color="red", icon="user", prefix="fa"),
).add_to(m)

# Vẽ tuyến đường đi thực tế bám theo đường bộ lên bản đồ
if route_coords:
  folium.PolyLine(
      locations=route_coords,
      color="blue",
      weight=5,
      opacity=0.8,
      tooltip=(
          f"Lộ trình tới {nearest_station['name']} (~{real_distance:.2f} km)"
      ),
  ).add_to(m)

# Hiển thị giao diện bố cục responsive (Tự động thích nghi màn hình máy tính & điện thoại)
col_map, col_info = st.columns([2, 1])

with col_map:
  st.subheader("🗺️ Bản đồ chỉ đường chi tiết")
  st_folium(m, width="100%", height=500)

with col_info:
  st.subheader("📊 Thông tin lộ trình")
  if nearest_station:
    st.success(f"**Trạm gần nhất:**\n\n🔹 **{nearest_station['name']}**")
    st.metric(
        label="Khoảng cách đường đi thực tế", value=f"{real_distance:.2f} km"
    )
    if travel_duration > 0:
      st.metric(
          label="Thời gian di chuyển dự kiến",
          value=f"{int(travel_duration)} phút",
      )

    st.write(
        f"📍 **Tọa độ trạm:** `{nearest_station['lat']},`"
        f" `{nearest_station['lon']}`"
    )

    maps_url = (
        f"https://www.google.com/maps/dir/?api=1&destination="
        f"{nearest_station['lat']},{nearest_station['lon']}"
    )
    st.markdown(
        f"[👉 Mở chỉ đường chi tiết trên Google Maps]({maps_url})",
        unsafe_allow_html=True,
    )
  else:
    st.warning("Không tìm thấy điểm dữ liệu phù hợp.")
