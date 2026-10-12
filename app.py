import math
from xml.etree import ElementTree as ET
import folium
from folium.plugins import LocateControl
import streamlit as st
from streamlit_folium import st_folium

st.set_page_config(
    page_title="Tìm Tủ Pin V-GREEN Từ Vị Trí Nhập Vào",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🔋 Tìm Đường Ngắn Nhất Đến Tủ Pin V-GREEN Từ Vị Trí Tùy Chỉnh")
st.markdown(
    "Nhập tọa độ hoặc địa điểm cần tìm kiếm để hệ thống so sánh với cơ sở dữ"
    " liệu 4 file bản đồ và tìm ra tủ pin gần nhất."
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


# Hàm đọc dữ liệu trạm từ file KML (bạn có thể đưa 4 file doc.kml vào cùng thư mục dự án)
def load_stations_from_kml(filename):
  stations_list = []
  try:
    tree = ET.parse(filename)
    root = tree.getroot()
    namespaces = {"kml": "http://www.opengis.net/kml/2.2"}
    for placemark in root.findall(".//kml:Placemark", namespaces):
      name_elem = placemark.find("kml:name", namespaces)
      coord_elem = placemark.find(".//kml:coordinates", namespaces)
      if name_elem is not None and coord_elem is not None:
        coords_text = coord_elem.text.strip().split()[0]
        parts = coords_text.split(",")
        if len(parts) >= 2:
          lon = float(parts[0])
          lat = float(parts[1])
          stations_list.append(
              {"name": name_elem.text.strip(), "lat": lat, "lon": lon}
          )
  except Exception:
    # Nếu chưa đưa đủ file vào thư mục thì bỏ qua để không lỗi app
    pass
  return stations_list


# Tự động quét dữ liệu từ 4 file KML nếu bạn đặt tên chúng trong thư mục dự án:
# 1. doc_phurieng.kml (hoặc tên tương ứng)
# Hoặc bạn có thể tải chúng trực tiếp ở Sidebar bên dưới:
st.sidebar.header("📁 Dữ liệu 4 file bản đồ")
uploaded_files = st.sidebar.file_uploader(
    "Tải lên 4 file bản đồ (.kml hoặc doc.kml)",
    type=["kml"],
    accept_multiple_files=True,
)

all_stations = []
if uploaded_files:
  for uploaded_file in uploaded_files:
    # Xử lý đọc file trực tiếp từ giao diện tải lên
    try:
      tree = ET.parse(uploaded_file)
      root = tree.getroot()
      namespaces = {"kml": "http://www.opengis.net/kml/2.2"}
      for placemark in root.findall(".//kml:Placemark", namespaces):
        name_elem = placemark.find("kml:name", namespaces)
        coord_elem = placemark.find(".//kml:coordinates", namespaces)
        if name_elem is not None and coord_elem is not None:
          coords_text = coord_elem.text.strip().split()[0]
          parts = coords_text.split(",")
          if len(parts) >= 2:
            all_stations.append({
                "name": name_elem.text.strip(),
                "lat": float(parts[1]),
                "lon": float(parts[0]),
            })
    except Exception as e:
      st.sidebar.error(f"Lỗi file {uploaded_file.name}: {e}")
  st.sidebar.success(f"Đã nạp tổng cộng {len(all_stations)} điểm từ các file!")
else:
  st.sidebar.info(
      "💡 Vui lòng tải các file `doc.kml` của 4 bản đồ lên đây để hệ thống có"
      " dữ liệu so sánh."
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

# Khởi tạo bản đồ tại vị trí tìm kiếm
m = folium.Map(
    location=st.session_state["search_loc"], zoom_start=13, tiles="OpenStreetMap"
)

# Đánh dấu các tủ pin trên 4 file
for stn in all_stations:
  folium.Marker(
      location=[stn["lat"], stn["lon"]],
      popup=stn["name"],
      icon=folium.Icon(color="green", icon="motorcycle", prefix="fa"),
  ).add_to(m)

# Đánh dấu vị trí cần tìm kiếm (Icon màu cam/đỏ)
target_lat, target_lon = st.session_state["search_loc"]
folium.Marker(
    location=[target_lat, target_lon],
    popup="Vị trí bạn đang tìm kiếm",
    icon=folium.Icon(color="orange", icon="crosshairs", prefix="fa"),
).add_to(m)

# Tính toán tìm tủ pin gần vị trí nhập vào nhất
nearest_station = None
min_dist = float("inf")

if all_stations:
  for stn in all_stations:
    dist = haversine(target_lat, target_lon, stn["lat"], stn["lon"])
    if dist < min_dist:
      min_dist = dist
      nearest_station = stn

  if nearest_station:
    # Vẽ đường nối từ vị trí nhập vào tới tủ pin gần nhất
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

  # Nếu chọn chế độ click bản đồ và người dùng bấm vào map
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
    st.warning("Vui lòng tải các file bản đồ lên ở thanh bên trái.")
