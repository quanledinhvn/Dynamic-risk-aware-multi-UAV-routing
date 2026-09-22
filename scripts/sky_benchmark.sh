#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(cd "$script_dir/.." && pwd -P)"

cluster="uav-benchmark"
config="phase1/configs/benchmark_p1_c25_r1.json"
instance_type="c7a.2xlarge"

workers="8"
spot="false"
keep_cluster_on_failure="false"

idle_minutes="15"
action=""
config_path=""
cleanup_armed="false"
cleanup_started="false"

usage() {
  cat <<'EOF'
Usage: scripts/sky_benchmark.sh ACTION [OPTIONS]

Actions:
  check       Validate local tools and SkyPilot AWS access
  launch      Launch the benchmark in detached mode
  logs        Follow benchmark logs
  download    Download artifacts from the latest run
  down        Terminate the cluster
  run         Launch, wait, download, and terminate

Options:
  --cluster NAME
  --config PATH
  --instance-type TYPE
  --workers N
  --spot
  --keep-cluster-on-failure
  -h, --help
EOF
}

die() {
  printf 'Lỗi: %s\n' "$1" >&2
  return 1
}

require_option_value() {
  local option="$1"
  local count="$2"

  if [[ "$count" -lt 2 ]]; then
    die "Thiếu giá trị cho $option."
  fi
}

parse_args() {
  if [[ "$#" -eq 0 ]]; then
    usage >&2
    return 1
  fi

  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    check|launch|logs|download|down|run)
      action="$1"
      shift
      ;;
    *)
      die "Lệnh không hợp lệ: $1"
      ;;
  esac

  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      --cluster)
        require_option_value "$1" "$#"
        cluster="$2"
        shift 2
        ;;
      --config)
        require_option_value "$1" "$#"
        config="$2"
        shift 2
        ;;
      --instance-type)
        require_option_value "$1" "$#"
        instance_type="$2"
        shift 2
        ;;
      --workers)
        require_option_value "$1" "$#"
        workers="$2"
        shift 2
        ;;
      --spot)
        spot="true"
        shift
        ;;
      --keep-cluster-on-failure)
        keep_cluster_on_failure="true"
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "Tùy chọn không hợp lệ: $1"
        ;;
    esac
  done
}

validate_inputs() {
  if [[ ! "$cluster" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
    die "Tên cluster không hợp lệ: $cluster"
  fi

  if [[ ! "$workers" =~ ^[1-9][0-9]*$ ]]; then
    die "workers phải là số nguyên dương."
  fi

  local candidate="$config"
  if [[ "$candidate" != /* ]]; then
    candidate="$repo_root/$candidate"
  fi

  if [[ ! -f "$candidate" ]]; then
    die "Config không tồn tại: $config"
  fi

  config_path="$(realpath "$candidate")"
  case "$config_path" in
    "$repo_root"/*)
      config="${config_path#"$repo_root/"}"
      ;;
    *)
      die "Config phải nằm trong repository: $config_path"
      ;;
  esac
}

require_command() {
  local command_name="$1"
  local display_name="$2"

  if ! command -v "$command_name" >/dev/null 2>&1; then
    die "$display_name chưa được cài đặt hoặc không có trong PATH."
  fi
}

check_preflight() {
  require_command sky SkyPilot
  require_command rsync rsync

  if [[ ! -f "$repo_root/infra/skypilot/benchmark.yaml" ]]; then
    die "Không tìm thấy SkyPilot task YAML."
  fi

  sky check aws
}

launch_benchmark() {
  check_preflight

  local run_id
  run_id="$(date -u +%Y%m%dT%H%M%SZ)"

  local remote_output="phase1/results/sky/$run_id"
  local task_file="$repo_root/infra/skypilot/benchmark.yaml"
  local launch_args=(
    launch --yes --detach-run --cluster "$cluster"
    --instance-type "$instance_type"
    --idle-minutes-to-autostop "$idle_minutes"
    --down --wait-for jobs
    --env "BENCHMARK_CONFIG=$config"
    --env "BENCHMARK_WORKERS=$workers"
    --env "BENCHMARK_OUTPUT_DIR=$remote_output"
  )

  if [[ "$spot" == "true" ]]; then
    printf '%s\n' \
      'Cảnh báo: Spot không có bảo đảm recovery hoặc checkpoint.' >&2
    launch_args+=(--use-spot)
  fi

  launch_args+=("$task_file")
  sky "${launch_args[@]}" || return $?

  local state_dir="$repo_root/.sky-benchmark"
  local state_file="$state_dir/$cluster.state"
  local state_tmp="$state_file.tmp.$$"
  mkdir -p "$state_dir"

  printf 'run_id=%s\nremote_output=%s\n' \
    "$run_id" "$remote_output" >"$state_tmp"
  mv "$state_tmp" "$state_file"
}

read_state() {
  local state_file="$repo_root/.sky-benchmark/$cluster.state"
  if [[ ! -f "$state_file" ]]; then
    die "Không tìm thấy state hợp lệ cho cluster $cluster."
  fi

  run_id=""
  remote_output=""
  local invalid="false"
  local key value

  while IFS='=' read -r key value; do
    case "$key" in
      run_id)
        if [[ -n "$run_id" ]]; then
          invalid="true"
        fi
        run_id="$value"
        ;;
      remote_output)
        if [[ -n "$remote_output" ]]; then
          invalid="true"
        fi
        remote_output="$value"
        ;;
      *)
        invalid="true"
        ;;
    esac
  done <"$state_file"

  if [[ "$invalid" == "true" || ! "$run_id" =~ ^[0-9]{8}T[0-9]{6}Z$ ]]; then
    die "Tệp state không hợp lệ: $state_file"
  fi

  if [[ "$remote_output" != "phase1/results/sky/$run_id" ]]; then
    die "Tệp state có remote output không hợp lệ."
  fi
}

download_artifacts() {
  require_command rsync rsync
  read_state

  local local_output="$repo_root/$remote_output"
  mkdir -p "$(dirname "$local_output")"

  rsync -az -- \
    "$cluster:~/sky_workdir/$remote_output/" \
    "$local_output/"
}

follow_logs() {
  require_command sky SkyPilot
  sky logs "$cluster" --follow
}

down_cluster() {
  require_command sky SkyPilot
  printf 'Đang hủy cluster: %s\n' "$cluster" >&2

  sky down --yes "$cluster"
}

cleanup_failed_run() {
  local status="$?"
  if [[ "$cleanup_armed" != "true" || "$status" -eq 0 ]]; then
    return
  fi

  if [[ "$cleanup_started" == "true" ]]; then
    return
  fi

  cleanup_started="true"
  cleanup_armed="false"
  trap '' INT TERM
  set +e

  printf 'Benchmark thất bại; đang lấy log hiện có.\n' >&2
  sky logs "$cluster" --no-follow >&2

  if [[ "$keep_cluster_on_failure" == "true" ]]; then
    printf '%s\n' \
      "Cluster được giữ lại để debug. Hãy chạy: scripts/sky_benchmark.sh down --cluster $cluster" >&2
  else
    down_cluster
  fi

  return "$status"
}

exit_for_signal() {
  local status="$1"
  exit "$status"
}

run_workflow() {
  trap cleanup_failed_run EXIT
  trap 'exit_for_signal 130' INT
  trap 'exit_for_signal 143' TERM
  cleanup_armed="true"

  launch_benchmark || return $?
  follow_logs || return $?
  download_artifacts || return $?

  down_cluster || return $?
  cleanup_armed="false"

  printf 'Kết quả đã tải về: %s\n' "$repo_root/$remote_output"
}

main() {
  parse_args "$@"
  validate_inputs

  case "$action" in
    check)
      check_preflight
      ;;
    launch)
      launch_benchmark
      ;;
    logs)
      follow_logs
      ;;
    download)
      download_artifacts
      ;;
    down)
      down_cluster
      ;;
    run)
      run_workflow
      ;;
  esac
}

main "$@"
