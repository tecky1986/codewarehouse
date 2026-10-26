#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

ts="$(date +%Y%m%d-%H%M)"
pkg="container-packing-windows-x64-${ts}.zip"

# Prefer a freshly built local Windows bundle if present.
if [ -d "release/windows/container_packing" ] && [ -f "release/windows/container_packing/container_packing.exe" ]; then
  src="release/windows/container_packing"
else
  src=""
fi

if [ -z "$src" ]; then
  if [ -n "${CP_WINDOWS_PACKAGE:-}" ] && [ -f "${CP_WINDOWS_PACKAGE:-}" ]; then
    workdir="$(mktemp -d)"
    unzip -q "${CP_WINDOWS_PACKAGE:-}" -d "$workdir"
    entry="$(find "$workdir" -maxdepth 2 -type f -name 'container_packing.exe' -print -quit)"
    if [ -z "$entry" ]; then
      echo "No container_packing.exe found in ${CP_WINDOWS_PACKAGE:-}." >&2
      exit 1
    fi
    src="$(cd "$(dirname "$entry")" && pwd)"
  else
    echo "Use CP_WINDOWS_PACKAGE=/path/to/windows.zip to repack a Windows bundle." >&2
    exit 1
  fi
fi

if ! head -c 2 "$src/container_packing.exe" | od -An -tx1 | grep -q '4d 5a'; then
  echo "container_packing.exe does not look like a Windows executable." >&2
  exit 1
fi

# Reuse the existing user guide if present, otherwise write the standard one.
if [ ! -f "$src/使用说明.txt" ]; then
  cat > "$src/使用说明.txt" <<'EOF'
集装箱装箱工具 Windows 版

1. 解压本压缩包
2. 双击 container_packing.exe
3. 浏览器会自动打开本地页面（数据保存在 %USERPROFILE%\.container-packing）

本包不含 Python 源码，请勿移动 _internal 目录。
EOF
fi

rm -f "$pkg"
# Normalize the top-level folder inside the archive to container_packing/.
tmpdir="$(mktemp -d)"
cp -a "$src" "$tmpdir/container_packing"
# Strip Python sources from the shipped bundle, keeping only compiled artifacts.
rm -f "$tmpdir/container_packing"/*.py "$tmpdir/container_packing"/*.pyi "$tmpdir/container_packing"/*.pyx || true
find "$tmpdir/container_packing" -name '*.py' -type f -print -delete
find "$tmpdir/container_packing" -name '*.pyi' -type f -print -delete
find "$tmpdir/container_packing" -name '*.pyx' -type f -print -delete

(
  cd "$tmpdir"
  zip -qr "/workspace/$pkg" container_packing
)

rm -rf "$tmpdir"
echo "已生成: $pkg"
