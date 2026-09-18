# 15 ĐỀ BÀI TỐI ƯU PHỤC VỤ NGHIÊN CỨU

## CHO HỌC PHẦN DESIGN AND ANALYSIS OF ALGORITHMS

## 1. Tiêu chí thiết kế đề bài

Các đề bài dưới đây không chỉ yêu cầu cài đặt một thuật toán có sẵn. Mỗi đề cần được phát triển theo hướng có khoảng trống nghiên cứu, bộ benchmark đã được công bố, baseline mạnh, cơ chế thuật toán mới và khả năng mở rộng sang đa mục tiêu, động, online hoặc bất định.

- Câu hỏi nghiên cứu cụ thể.
- Mô hình hóa rõ input, output, mục tiêu và ràng buộc.
- Thuật toán baseline chuẩn và đề xuất ít nhất một cơ chế cải tiến có thể kiểm chứng.
- Phân tích độ phức tạp, tính khả thi, cận chất lượng hoặc expected-time khi phù hợp.
- Thực nghiệm: bộ dữ liệu benchmark đã công bố, seed ngẫu nhiên, lặp lại, kiểm định thống kê.
- Đánh giá objective, runtime, robustness, feasibility, scalability và sensitivity.

## 2. Danh sách 15 đề bài có tiềm năng nghiên cứu

| # | Đề bài nghiên cứu | Hướng đóng góp thuật toán | Dataset/benchmark công khai | Bài báo tham khảo gần và sát nhất |
|---:|---|---|---|---|
| 1 | Dynamic risk-aware multi-UAV routing | Tái tối ưu route đa UAV khi risk map, deadline, pin và mục tiêu thay đổi; rolling-horizon ALNS/NSGA-III có risk-priority repair. | Solomon/Homberger VRPTW + RescueNet/C2A. | Pu et al., “Dynamic task allocation for multi-UAVs in disaster scenarios” (2026): phân công nhiệm vụ khẩn cấp động, đa loại tác vụ, swarm UAV trong thiên tai. |
| 2 | Deadline-constrained multi-UAV risk coverage | Tối đa risk coverage trước deadline dưới ràng buộc pin; greedy adaptive, submodular orienteering hoặc approximation-aware heuristic. | OR-Library Set Cover/Maximum Coverage + RescueNet/C2A. | Chandran & Vipin, “Multi-UAV Networks for Disaster Monitoring: Challenges and Opportunities from a Network Perspective” (2024): coverage, coordination, communication, monitoring trong thiên tai. |
| 3 | Multi-UAV path planning với vùng cấm bay động | Graph search + metaheuristic/repair để tránh no-fly zones, gió và vùng nguy hiểm biến đổi theo thời gian. | OpenStreetMap; NASA SRTM/DEM; NOAA/Open-Meteo; instance tái lập. | Cheaitou et al., “Optimizing and visualizing dynamic service performance for …” (2026): gán UAV vào flight paths khả thi, không xung đột, theo bài toán routing mở rộng. |
| 4 | UAV-IoT data collection tối ưu AoI | Đồng tối ưu route, thứ tự thu thập, hover time, truyền dữ liệu để giảm AoI, năng lượng và alert delay. | Solomon VRPTW + topology IoT/UAV tái lập. | Tekin et al., “Age of Information minimization for secure data collection …” (2025): mô hình MIP tối thiểu average AoI và số UAV cần dùng. |
| 5 | Joint UAV trajectory–relay–bandwidth allocation | Phân rã quỹ đạo, relay selection, bandwidth/power allocation để tối đa timely-alert probability và connectivity. | SNDlib; Topology Zoo + target từ RescueNet. | Huang et al., “Dynamic Dual-Antenna Time-Slot Allocation Protocol for UAV-Aided Relaying System Under Probabilistic LoS-Channel” (2025): time-slot, power, trajectory cho UAV relay. |
| 6 | Robust UAV mission planning dưới bất định thời tiết | Chance-constrained/distributionally robust route planning với gió, mưa, suy giảm pin; tối đa mission success probability. | NOAA/Open-Meteo + Solomon/Homberger + RescueNet/C2A. | Zerrouk et al., “Increasing Automation on Mission Planning for …” (2025): tối ưu cộng tác drone tại chỗ cho situation awareness trong thiên tai. |
| 7 | QUBO decomposition cho task allocation và trajectory UAV | Phân rã assignment, waypoint, time-slot scheduling thành QUBO nhỏ; evolutionary coordination và repair constraints. | TSPLIB/CVRPLIB + RescueNet/C2A. | Qi et al., “Three-learning strategy particle swarm optimization for air …” (2025): tối ưu đồng thời đường đi và lịch trình vehicle–drone; baseline metaheuristic tham khảo. |
| 8 | UAV charging-station placement và fleet sizing | Facility location tối ưu trạm sạc, số UAV, vùng phục vụ để giảm response time, energy và uncovered risk. | TSPLIB coordinates; OpenStreetMap; RescueNet/C2A. | Wang et al., “UAV–Ground Vehicle Collaborative Delivery in Emergency …” (2025): trajectory optimization nhiều pha và phối hợp UAV–ground vehicle trong emergency delivery. |
| 9 | Safe MARL cho swarm UAV | Kết hợp MARL với safety shield, MPC hoặc combinatorial repair cho pin, tránh va chạm, no-fly zones và connectivity. | AirSim; PX4/Gazebo; UAVBench; scenario RescueNet/C2A. | Zha et al., “Large-Scale UAV Swarm Coordination for Sensing and …” (2026): swarm coordination quy mô lớn cho sensing, path planning và routing optimization. |
| 10 | Vision-guided online UAV alert prioritization | Dùng risk score từ ảnh để chọn frame/tile/target cần truyền/xử lý trước với compute và bandwidth hữu hạn. | RescueNet; C2A; AIDER; DisasterEye. | Tiggeloven et al., “The role of artificial intelligence for early warning systems” (2025): AI trong EWS, cơ hội/thách thức chuyển AI thành quyết định cảnh báo. |
| 11 | Energy-aware edge offloading cho UAV disaster analytics | Joint offloading, UAV-BS/edge placement, scheduling, cache để giảm latency, energy và deadline violation. | Alibaba Cluster Trace; Google Cluster Data + RescueNet/C2A workloads. | Azfar et al., “Enhancing Disaster Resilience with UAV-Assisted Edge …” (2025): UAV relay/edge, power allocation và trajectory cho resilient coverage. |
| 12 | Dynamic min-cost flow cho mạng relay UAV | Cập nhật nhanh data routes đa chặng sau link failure, congestion hoặc UAV hết pin; dynamic flow thay vì solve-from-scratch. | SNDlib; Topology Zoo; Internet2/GEANT. | Ni et al., “A computerized intelligent system for UAV communication …” (2026): hệ thống relay UAV khẩn cấp tích hợp sensing thông minh và cooperative operation. |
| 13 | UAV swarm formation và coverage có ràng buộc liên lạc | Đồng tối ưu formation, sensing coverage, redundancy, collision risk và network connectivity; graph-based evolutionary optimization. | C2A/RescueNet target map; AirSim/PX4 simulation. | “Reliability- and Connectivity-Constrained Age-of-Information Optimization for UAV Swarm IoT Data Collection” (2026): joint assignment, motion, time allocation, power, freshness, reliability, connectivity. |
| 14 | Multi-UAV search-and-rescue với xác suất phát hiện | Tối ưu search order, phân vùng, route, hover time dưới detection probability không đồng nhất. | RescueNet; C2A; xView; AIDER; detection map tổng hợp. | “Risk-sensitive mean-field control of large-scale UAV …” (2026): risk-sensitive mean-field optimal control cho multi-UAV tracking, guidance, first response. |
| 15 | UAV–ground vehicle collaborative emergency delivery | Joint routing, rendezvous, launch/recovery, charging để giảm delivery time, energy, tardiness. | CVRPLIB; Solomon/Homberger; TSPLIB; OpenStreetMap. | Wang et al., “UAV–Ground Vehicle Collaborative Delivery in Emergency …” (2025): phối hợp delivery và trajectory qua pha takeoff, cruise, hover, landing. |

## 3. Lộ trình triển khai

| Thời gian | Yêu cầu tối thiểu | Bằng chứng nghiên cứu cần bổ sung |
|---|---|---|
| Tuần 1–2 | Mô hình + baseline + benchmark nhỏ | Phân tích complexity, objective và runtime |
| Tuần 3–6 | Thuật toán cải tiến + benchmark đầy đủ/ Trình bày ý tưởng | Ablation, sensitivity, 20–30 seed, kiểm định thống kê |
| Tuần 7–9 | Novel mechanism rõ ràng / Trình bày kết quả | So sánh SOTA, reproducibility package, case study |
| Tuần 10 | Nộp báo cáo | Abstract, Introduction, Related Work, Proposed Method, Experiment Results, Discussion, Conclusion |

## 4. Yêu cầu giao bài tập theo hai pha

**Pha 1 – bắt buộc:** cài đặt thuật toán baseline trên bộ dữ liệu benchmark đã công bố, có báo cáo kết quả và mã nguồn cài đặt.

**Pha 2 – nghiên cứu:** chọn ít nhất một hướng mở rộng:

- Đa mục tiêu.
- Tối ưu động/online.
- Bất định/stochastic/robust.
- Prediction-aware optimization.
- Learning-assisted heuristic.
- Decomposition/parallelization.
- Constraint repair.
- Approximation/guarantee.
- Optimization inspired by quantum/QUBO.
- Công bằng, rủi ro và độ tin cậy.

Báo cáo cần viết theo cấu trúc của bài nghiên cứu khoa học như một bài báo: Abstract, Introduction, Related Work, Proposed Method, Experiment Results, Discussion, Conclusion.
