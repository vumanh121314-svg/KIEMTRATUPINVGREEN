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

# Cấu hình giao diện & Responsive trên mọi thiết bị
st.set_page_config(
    page_title="Hệ Thống Trạm Đổi Pin V-GREEN",
    layout="wide",
    initial_sidebar_state="auto",
)

# --- TÙY CHỈNH GIAO DIỆN BACKGROUND & THƯƠNG HIỆU V-GREEN ---
st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
    }
    .main-header {
        background-color: #15803d;
        color: white;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .stButton>button {
        background-color: #16a34a;
        color: white;
        border-radius: 8px;
        border: none;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #15803d;
        color: white;
    }
    </style>
    <div class="main-header">
        <h1>🔋 V-GREEN - HỆ THỐNG TỦ ĐỔI PIN THÔNG MINH</h1>
        <p>Tìm đường đi chính xác tới các tủ pin gần vị trí của bạn nhất</p>
    </div>
""",
    unsafe_allow_html=True,
)


# Hàm gọi API OSRM lấy tuyến đường thực tế (Đã tối ưu cache và lấy thêm thời gian di chuyển)
@st.cache_data
def get_osrm_route(lat1, lon1, lat2, lon2):
    url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if "routes" in data and len(data["routes"]) > 0:
                route = data["routes"][0]
                distance_km = route["distance"] / 1000.0
                duration_min = route["duration"] / 60.0  # Thời gian tính bằng phút
                coords = route["geometry"]["coordinates"]
                latlon_coords = [[c[1], c[0]] for c in coords]
                return distance_km, duration_min, latlon_coords
    except Exception:
        pass
    return None, None, None


# Hàm tính khoảng cách phụ trợ (Haversine)
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


# Hàm đọc file KMZ/KML chứa dữ liệu tủ pin và thông tin khách hàng
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
                desc_elem = placemark.find("kml:description", namespaces)
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
                                else "Tủ pin không tên"
                            )
                            description = (
                                desc_elem.text.strip()
                                if desc_elem is not None and desc_elem.text
                                else "Chưa có thông tin khách hàng / ghi chú"
                            )
                            stations_list.append({
                                "name": name,
                                "lat": lat,
                                "lon": lon,
                                "customer_info": description,
                            })
                        except ValueError:
                            continue
    except Exception as e:
        st.error(f"Lỗi khi đọc file {file_path}: {e}")
    return stations_list


@st.cache_data
def load_all_kmz_files():
    all_stations = []
    kmz_files = [f for f in os.listdir(".") if f.endswith(".kmz")]
    for file in kmz_files:
        stations = load_stations_from_kmz_path(file)
        all_stations.extend(stations)
    return all_stations, kmz_files


with st.spinner("Đang tải dữ liệu các tủ pin V-GREEN..."):
    all_stations, found_files = load_all_kmz_files()

st.sidebar.success(
    f"🔋 Đã nạp thành công {len(all_stations)} tủ pin từ {len(found_files)}"
    " file KMZ!"
)

# --- XÁC ĐỊNH VỊ TRÍ NGƯỜI DÙNG ---
st.sidebar.markdown("---")
st.sidebar.header("📍 Vị trí của bạn")

st.sidebar.subheader("1. Lấy vị trí GPS tự động")
loc = streamlit_geolocation()

default_lat, default_lon = 11.50567, 106.88714

if loc and loc.get("latitude") and loc.get("longitude"):
    current_lat = loc["latitude"]
    current_lon = loc["longitude"]
    st.sidebar.success("Đã định vị thành công vị trí hiện tại!")
else:
    current_lat, current_lon = default_lat, default_lon

st.sidebar.markdown("---")
st.sidebar.subheader("2. Hoặc nhập tọa độ thủ công")
entered_lat = st.sidebar.number_input(
    "Vĩ độ (Lat)", value=float(current_lat), format="%.6f"
)
entered_lon = st.sidebar.number_input(
    "Kinh độ (Lon)", value=float(current_lon), format="%.6f"
)

target_lat, target_lon = entered_lat, entered_lon

# Tính toán khoảng cách chim bay tới tất cả các tủ pin để sắp xếp
station_options = []
if all_stations:
    for stn in all_stations:
        dist_hb = haversine(target_lat, target_lon, stn["lat"], stn["lon"])
        station_options.append({"station": stn, "dist_hb": dist_hb})

    station_options = sorted(station_options, key=lambda x: x["dist_hb"])

# --- LỰA CHỌN TỦ PIN ---
st.sidebar.markdown("---")
st.sidebar.header("🚏 Chọn tủ pin muốn xem đường đi")

top_stations = station_options[:10]
station_labels = [
    f"{item['station']['name']} (~{item['dist_hb']:.2f} km)"
    for item in top_stations
]

selected_label = st.sidebar.selectbox(
    "Danh sách các tủ pin gần bạn:", station_labels
)

selected_index = station_labels.index(selected_label)
chosen_station = top_stations[selected_index]["station"]

# TỰ ĐỘNG TÍNH TOÁN KHOẢNG CÁCH VÀ LỘ TRÌNH ĐƯỜNG BỘ THỰC TẾ
real_distance, route_duration, route_coords = get_osrm_route(
    target_lat, target_lon, chosen_station["lat"], chosen_station["lon"]
)

if real_distance is None:
    real_distance = top_stations[selected_index]["dist_hb"]
    route_duration = real_distance * 3  # Ước tính thời gian tạm tính nếu mất kết nối mạng
    route_coords = [
        [target_lat, target_lon],
        [chosen_station["lat"], chosen_station["lon"]],
    ]

# --- KHỞI TẠO BẢN ĐỒ FOCUS VÀO TỦ ĐƯỢC CHỌN ---
m = folium.Map(
    location=[chosen_station["lat"], chosen_station["lon"]],
    zoom_start=15,
    tiles="OpenStreetMap",
)

# Đánh dấu các tủ pin xung quanh
for item in top_stations:
    stn = item["station"]
    folium.Marker(
        location=[stn["lat"], stn["lon"]],
        popup=stn["name"],
        icon=folium.Icon(color="green", icon="battery-full", prefix="fa"),
    ).add_to(m)

# Đánh dấu tủ pin đang được chọn (màu cam)
folium.Marker(
    location=[chosen_station["lat"], chosen_station["lon"]],
    popup=f"Đang chọn: {chosen_station['name']}",
    icon=folium.Icon(color="orange", icon="bolt", prefix="fa"),
).add_to(m)

# Đánh dấu vị trí của bạn (màu đỏ)
folium.Marker(
    location=[target_lat, target_lon],
    popup="Vị trí của bạn",
    icon=folium.Icon(color="red", icon="user", prefix="fa"),
).add_to(m)

# Vẽ tuyến đường đi thực tế bám theo đường bộ
if route_coords:
    folium.PolyLine(
        locations=route_coords,
        color="blue",
        weight=5,
        opacity=0.8,
        tooltip=f"Lộ trình tới {chosen_station['name']}",
    ).add_to(m)

# --- HIỂN THỊ GIAO DIỆN CHÍNH ---
col_map, col_info = st.columns([2, 1])

with col_map:
    st.subheader("🗺️ Bản đồ định vị & Lộ trình đổi pin")
    st_folium(m, width="100%", height=500)

with col_info:
    st.subheader("📊 Thông tin tủ pin đã chọn")
    st.success(f"**Tủ đổi pin:**\n\n🔹 **{chosen_station['name']}**")
    
    st.info(f"👤 **Thông tin khách hàng / Ghi chú:**\n\n{chosen_station.get('customer_info', 'Không có thông tin')}")

    # Hiển
