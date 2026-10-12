import math
import xml.etree.ElementTree as ET
import folium
import streamlit as st
from streamlit_folium import st_folium

st.set_page_config(
    page_title="Tìm Tủ Pin V-GREEN Gần Nhất",
    layout="wide",
)

st.title("🔋 Tìm Khoảng Cách Ngắn Nhất Đến Tủ Pin V-GREEN Từ File KML")

# Tạo thanh công cụ bên trái (Sidebar) để tải file KML lên
st.sidebar.header("📁 Tải dữ liệu bản đồ")
uploaded_file = st.sidebar.file_uploader(
    "Tải lên file KML của bạn (ví dụ: doc.kml)", type=["kml", "KMZ"]
)


# Hàm tính khoảng cách Haversine giữa 2 tọa độ GPS (km)
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


# Hàm đọc dữ liệu từ file KML được tải lên
def load_stations_from_uploaded_file(kml_file):
  stations_list = []
  try:
    tree = ET.parse(kml_file)
    root = tree.getroot()
    namespaces = {"kml": "http://www.opengis.net/kml/2.2"}
    for placemark in root.findall(".//kml:Placemark", namespaces):
      name_elem = placemark.find("kml:name", namespaces)
      coord_elem = placemark.find(".//kml:coordinates", namespaces)
      if name_elem is not None and coord_elem is not None:
        coords_text = coord_elem.text.strip()
        parts = coords_text.split(",")
        if len(parts) >= 2:
          lon = float(parts[0])
          lat = float(parts[1])
          stations_list.append(
              {
                  "name": (
                      name_elem.text
                      if name_elem.text
                      else "Tủ pin V-GREEN"
                  ),
                  "lat": lat,
                  "lon": lon,
              }
          )
  except Exception as e:
    st.sidebar.error(f"Lỗi đọc file KML: {e}")
  return stations_list


# Nạp dữ liệu tủ pin từ file người dùng upload
stations = []
if uploaded_file is not None:
  stations = load_stations_from_uploaded_file(uploaded_file)
  st.sidebar.success(f"Đã tải thành công {len(stations)} điểm tủ pin!")
else:
  st.sidebar.warning(
      "⚠️ Vui lòng tải file `.kml` lên ở khung trên để hiển thị bản đồ tủ pin."
  )

if not stations:
  st.info(
      "👈 Hãy tải file KML của bạn lên thông qua bảng điều khiển bên trái để bắt"
      " đầu."
  )
else:
  # Thiết lập tọa độ mặc định ban đầu dựa trên điểm đầu tiên của file
  default_lat = stations[0]["lat"]
  default_lon = stations[0]["lon"]

  if "current_loc" not in st.session_state:
    st.session_state["current_loc"] = (default_lat, default_lon)

  # Khởi tạo bản đồ
  m = folium.Map(
      location=st.session_state["current_loc"],
      zoom_start=13,
      tiles="OpenStreetMap",
  )

  # Đánh dấu các tủ pin lên bản đồ (Icon màu xanh lá)
  for stn in stations:
    folium.Marker(
        location=[stn["lat"], stn["lon"]],
        popup=stn["name"],
        icon=folium.Icon(color="green", icon="motorcycle", prefix="fa"),
    ).add_to(m)

  # Đánh dấu vị trí hiện tại của bạn (Icon màu đỏ)
  curr_lat, curr_lon = st.session_state["current_loc"]
  folium.Marker(
      location=[curr_lat, curr_lon],
      popup="Vị trí hiện tại của bạn",
      icon=folium.Icon(color="red", icon="user", prefix="fa"),
  ).add_to(m)

  # Tìm tủ pin gần nhất
  nearest_station = None
  min_dist = float("inf")

  for stn in stations:
    dist = haversine(curr_lat, curr_lon, stn["lat"], stn["lon"])
    if dist < min_dist:
      min_dist = dist
      nearest_station = stn

  # Vẽ đường nối ngắn nhất tới tủ pin gần nhất
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
            f"Đường đi tới {nearest_station['name']} (~{min_dist:.2f} km)"
        ),
    ).add_to(m)

  # Giao diện hiển thị chia 2 cột
  col1, col2 = st.columns([2, 1])

  with col1:
    st.subheader("🗺️ Bản đồ tương tác")
    st.markdown(
        "💡 *Bấm vào bất kỳ vị trí nào trên bản đồ để đổi điểm xuất phát (vị trí"
        " của bạn).*y"
    )
    output = st_folium(m, width="100%", height=550)

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
    st.subheader("📊 Kết quả tính toán")
    if nearest_station:
      st.success(
          f"**Tủ pin gần nhất:** \n\n🔹 **{nearest_station['name']}**"
      )
      st.metric(
          label="Khoảng cách đường chim bay", value=f"{min_dist:.2f} km"
      )
      st.write(
          f"📍 **Tọa độ tủ pin:** `{nearest_station['lat']},`"
          f" `{nearest_station['lon']}`"
      )
      st.write(
          f"📍 **Tọa độ vị trí hiện tại:** `{curr_lat:.5f},`"
          f" `{curr_lon:.5f}`"
      )

      # Link mở chỉ đường trực tiếp qua Google Maps ngoài trình duyệt
      maps_url = (
          f"https://www.google.com/maps/dir/?api=1&destination="
          f"{nearest_station['lat']},{nearest_station['lon']}"
      )
      st.markdown(
          f"[👉 Mở chỉ đường chi tiết trên Google Maps]({maps_url})",
          unsafe_allow_html=True,
      )
