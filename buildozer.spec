[app]
title = Georadar PI-3D
package.name = georadar_pi3d
package.domain = org.georadar
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,wav
version = 1.0
requirements = python3,kivy,pyjnius
android.permissions = BLUETOOTH, BLUETOOTH_ADMIN, BLUETOOTH_CONNECT, BLUETOOTH_SCAN, VIBRATE
android.api = 34
android.minapi = 21
orientation = landscape
fullscreen = 1
android.archs = arm64-v8a

[buildozer]
log_level = 2
warn_on_root = 1
