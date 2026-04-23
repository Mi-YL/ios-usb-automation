#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WDA_PROJECT_DEFAULT="$ROOT_DIR/vendor/WebDriverAgent/WebDriverAgent.xcodeproj"
DERIVED_DATA_DEFAULT="$ROOT_DIR/.wda_build/derived_data"

DEVICE_ID="${DEVICE_ID:-${1:-}}"
TEAM_ID="${TEAM_ID:-}"
PRODUCT_BUNDLE_ID="${PRODUCT_BUNDLE_ID:-com.myl.WebDriverAgentRunner}"
WDA_PROJECT="${WDA_PROJECT:-$WDA_PROJECT_DEFAULT}"
DERIVED_DATA_PATH="${DERIVED_DATA_PATH:-$DERIVED_DATA_DEFAULT}"
SCHEME="${SCHEME:-WebDriverAgentRunner}"
CONFIGURATION="${CONFIGURATION:-Debug}"
SIGNING_STYLE="${SIGNING_STYLE:-auto}"
PROVISIONING_PROFILE_UUID="${PROVISIONING_PROFILE_UUID:-}"
INSTALL_APP="${INSTALL_APP:-1}"
VERIFY_LAUNCH="${VERIFY_LAUNCH:-1}"
STRIP_OPTIONAL_FRAMEWORKS="${STRIP_OPTIONAL_FRAMEWORKS:-1}"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "缺少命令: $1" >&2
    exit 1
  fi
}

derive_team_id() {
  security find-identity -v -p codesigning \
    | sed -n 's/.*Apple Development: .* (\([A-Z0-9]\{10\}\)).*/\1/p' \
    | head -n1
}

derive_codesign_identity() {
  local team_id="$1"
  security find-identity -v -p codesigning \
    | sed -n "s/.*\"\(Apple Development: .* (${team_id})\)\".*/\1/p" \
    | head -n1
}

profile_path_from_uuid() {
  local uuid="$1"
  echo "$HOME/Library/Developer/Xcode/UserData/Provisioning Profiles/$uuid.mobileprovision"
}

profile_team_id() {
  local profile_path="$1"
  security cms -D -i "$profile_path" \
    | plutil -extract TeamIdentifier.0 raw -o - -
}

sign_path() {
  local path="$1"
  if [[ -e "$path" ]]; then
    codesign \
      --force \
      --sign "$CODESIGN_IDENTITY" \
      --preserve-metadata=identifier,entitlements \
      --generate-entitlement-der \
      "$path"
  fi
}

remove_launch_blocking_frameworks() {
  local app_path="$1"

  find "$app_path" \
    \( -path '*/Frameworks/XC*.framework' -o -path '*/Frameworks/XC*.dylib' \) \
    -print0 \
    | while IFS= read -r -d '' path; do
        rm -rf "$path"
      done

  if [[ "$STRIP_OPTIONAL_FRAMEWORKS" == "1" ]]; then
    find "$app_path" \
      \( -path '*/Frameworks/Testing.framework' -o -path '*/Frameworks/libXCTestSwiftSupport.dylib' \) \
      -print0 \
      | while IFS= read -r -d '' path; do
          rm -rf "$path"
        done
  fi
}

resign_bundle_tree() {
  local app_path="$1"

  while IFS= read -r -d '' path; do
    sign_path "$path"
  done < <(
    find "$app_path" \
      \( -name '*.framework' -o -name '*.dylib' -o -name '*.appex' -o -name '*.xctest' \) \
      -print0 \
      | awk 'BEGIN { RS="\0"; ORS="\0" } { paths[NR]=$0 } END { for (i=NR; i>=1; i--) print paths[i] }'
  )

  sign_path "$app_path"
}

install_app_to_device() {
  local device_id="$1"
  local app_path="$2"
  xcrun devicectl device install app --device "$device_id" "$app_path"
}

verify_launch() {
  local device_id="$1"
  local bundle_id="$2"
  xcrun devicectl device process launch \
    --device "$device_id" \
    --terminate-existing \
    --activate \
    "$bundle_id"
}

require_command xcodebuild
require_command xcrun
require_command security
require_command codesign
require_command /usr/libexec/PlistBuddy

if [[ -z "$DEVICE_ID" ]]; then
  echo "用法: DEVICE_ID=<udid> $0" >&2
  exit 1
fi

if [[ ! -d "$WDA_PROJECT" ]]; then
  echo "未找到 WDA 工程: $WDA_PROJECT" >&2
  exit 1
fi

if [[ -z "$TEAM_ID" ]]; then
  if [[ -n "$PROVISIONING_PROFILE_UUID" ]]; then
    PROFILE_PATH="$(profile_path_from_uuid "$PROVISIONING_PROFILE_UUID")"
    if [[ ! -f "$PROFILE_PATH" ]]; then
      echo "未找到 provisioning profile: $PROFILE_PATH" >&2
      exit 1
    fi
    TEAM_ID="$(profile_team_id "$PROFILE_PATH")"
  else
    TEAM_ID="$(derive_team_id)"
  fi
fi

if [[ -z "$TEAM_ID" ]]; then
  echo "未找到 Apple Development Team ID，请显式设置 TEAM_ID" >&2
  exit 1
fi

CODESIGN_IDENTITY="${CODESIGN_IDENTITY:-$(derive_codesign_identity "$TEAM_ID")}"
if [[ -z "$CODESIGN_IDENTITY" ]]; then
  echo "未找到 Team ID=$TEAM_ID 对应的 Apple Development 签名证书" >&2
  if [[ -n "$PROVISIONING_PROFILE_UUID" ]]; then
    echo "当前 provisioning profile 的 Team ID 与本机私钥/证书不匹配。" >&2
  fi
  exit 1
fi

mkdir -p "$DERIVED_DATA_PATH"

echo "==> Build WDA for testing"
xcodebuild_args=(
  build-for-testing \
  -project "$WDA_PROJECT" \
  -scheme "$SCHEME" \
  -configuration "$CONFIGURATION" \
  -destination "id=$DEVICE_ID" \
  -derivedDataPath "$DERIVED_DATA_PATH" \
  DEVELOPMENT_TEAM="$TEAM_ID" \
  PRODUCT_BUNDLE_IDENTIFIER="$PRODUCT_BUNDLE_ID" \
)

if [[ "$SIGNING_STYLE" == "manual" ]]; then
  if [[ -z "$PROVISIONING_PROFILE_UUID" ]]; then
    echo "SIGNING_STYLE=manual 时需要设置 PROVISIONING_PROFILE_UUID" >&2
    exit 1
  fi
  xcodebuild_args+=(
    CODE_SIGN_STYLE=Manual
    "PROVISIONING_PROFILE=$PROVISIONING_PROFILE_UUID"
  )
else
  xcodebuild_args+=(
    -allowProvisioningUpdates
    CODE_SIGN_STYLE=Automatic
  )
fi

xcodebuild "${xcodebuild_args[@]}"

APP_PATH="$(find "$DERIVED_DATA_PATH/Build/Products" -maxdepth 2 -type d -name 'WebDriverAgentRunner-Runner.app' | head -n1)"

if [[ -z "$APP_PATH" ]]; then
  echo "构建成功但未找到 WebDriverAgentRunner-Runner.app" >&2
  exit 1
fi

echo "==> Built app: $APP_PATH"

echo "==> Remove XCTest frameworks for devicectl launch"
remove_launch_blocking_frameworks "$APP_PATH"

echo "==> Re-sign app after stripping frameworks"
resign_bundle_tree "$APP_PATH"

APP_BUNDLE_ID="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$APP_PATH/Info.plist")"

echo "==> Final app bundle id: $APP_BUNDLE_ID"

if [[ "$INSTALL_APP" == "1" ]]; then
  echo "==> Install app to device"
  install_app_to_device "$DEVICE_ID" "$APP_PATH"
fi

if [[ "$VERIFY_LAUNCH" == "1" ]]; then
  echo "==> Verify devicectl launch"
  verify_launch "$DEVICE_ID" "$APP_BUNDLE_ID"
fi

echo
echo "完成。"
echo "设备 UDID: $DEVICE_ID"
echo "WDA app: $APP_PATH"
echo "Bundle ID: $APP_BUNDLE_ID"
