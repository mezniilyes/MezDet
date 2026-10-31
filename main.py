import os
import random
from datetime import datetime
from pathlib import Path

# Configuration Kivy avant les imports graphiques.
# Sur Android, laisser Kivy choisir son backend graphique.
if os.environ.get("ANDROID_ARGUMENT"):
    os.environ.pop("KIVY_GL_BACKEND", None)
    os.environ.pop("KIVY_GRAPHICS", None)
else:
    os.environ.setdefault("KIVY_GL_BACKEND", "angle_sdl2")

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.utils import get_color_from_hex, platform
from kivy.core.audio import SoundLoader
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.progressbar import ProgressBar

try:
    from plyer import vibrator
except ImportError:
    vibrator = None


def rgb(hex_color):
    return get_color_from_hex(hex_color)


class MatrixScanner(GridLayout):
    """Grille de visualisation 12 x 12."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cols = 12
        self.rows = 12
        self.spacing = dp(2)
        self.cells = []

        for _ in range(144):
            cell = Label(text="")
            cell.cell_color = rgb("#1E293B")
            with cell.canvas.before:
                Color(*cell.cell_color)
                cell.rect = Rectangle(pos=cell.pos, size=cell.size)
            cell.bind(pos=self._update_rect, size=self._update_rect)
            self.add_widget(cell)
            self.cells.append(cell)

    @staticmethod
    def _update_rect(cell, _value):
        cell.rect.pos = cell.pos
        cell.rect.size = cell.size

    def update_voxel(self, x, y, signal, metal):
        if not (0 <= x < 12 and 0 <= y < 12):
            return

        index = x * 12 + y
        if signal < 40:
            shade = "#1D4ED8" if metal == "VOID" else "#1E293B"
        elif metal == "GOLD/COPPER":
            shade = "#F59E0B"
        elif metal == "IRON/FERROUS":
            shade = "#64748B"
        elif metal == "VOID":
            shade = "#1D4ED8"
        else:
            shade = "#3B82F6"

        cell = self.cells[index]
        cell.cell_color = rgb(shade)
        cell.canvas.before.clear()
        with cell.canvas.before:
            Color(*cell.cell_color)
            cell.rect = Rectangle(pos=cell.pos, size=cell.size)


class AestheticCard(BoxLayout):
    """Carte avec fond et bordure arrondis."""

    def __init__(self, bg_color="#111827", border_color="#1E293B", **kwargs):
        super().__init__(**kwargs)
        self.bg_color = bg_color
        self.border_color = border_color
        self.bind(pos=self._update_shapes, size=self._update_shapes)
        self._update_shapes(self, None)

    def _update_shapes(self, _instance, _value):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*rgb(self.border_color))
            self.border_rect = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[dp(8)]
            )
            Color(*rgb(self.bg_color))
            inner_pos = (self.x + dp(1), self.y + dp(1))
            inner_size = (
                max(0, self.width - dp(2)),
                max(0, self.height - dp(2)),
            )
            self.bg_rect = RoundedRectangle(
                pos=inner_pos, size=inner_size, radius=[dp(7)]
            )


class UnifiedGeoradarApp(App):
    title = "GEORADAR PI-3D"

    def build(self):
        self.cur_x = 0
        self.cur_y = 0
        self.smartphone_mode = "SONORE"
        self.detect_sound = SoundLoader.load("ping.wav")
        self.android_stream = None
        self.bluetooth_socket = None
        self.rx_buffer = ""
        self.last_alert_state = None
        self.log_path = None

        if platform == "android":
            self.android_stream = self.connect_android_bluetooth("HC-05")

        main_layout = BoxLayout(
            orientation="vertical", padding=dp(12), spacing=dp(10)
        )
        with main_layout.canvas.before:
            Color(*rgb("#0B0F19"))
            self.bg_window = Rectangle(
                pos=main_layout.pos, size=main_layout.size
            )
        main_layout.bind(pos=self._update_background, size=self._update_background)

        # En-tête et commandes d'alerte.
        header_bar = BoxLayout(
            orientation="horizontal", size_hint_y=0.08, spacing=dp(5)
        )
        lbl_brand = Label(
            text="[b]GEORADAR PI-3D[/b] [color=38BDF8]LABORATORY EDITION[/color]",
            font_size="15sp",
            markup=True,
            size_hint_x=0.6,
            halign="left",
        )
        lbl_brand.bind(size=lbl_brand.setter("text_size"))
        header_bar.add_widget(lbl_brand)

        settings_box = BoxLayout(
            orientation="horizontal",
            spacing=dp(5),
            size_hint_x=0.4,
            padding=[0, dp(2)],
        )
        self.btn_sound_ico = Button(
            text="SON",
            font_size="10sp",
            bold=True,
            background_normal="",
            background_color=rgb("#10B981"),
        )
        self.btn_vibe_ico = Button(
            text="VIBREUR",
            font_size="10sp",
            bold=True,
            background_normal="",
            background_color=rgb("#1E293B"),
        )
        self.btn_sound_ico.bind(
            on_press=lambda _button: self.switch_hardware_alert("SONORE")
        )
        self.btn_vibe_ico.bind(
            on_press=lambda _button: self.switch_hardware_alert("VIBREUR")
        )
        settings_box.add_widget(self.btn_sound_ico)
        settings_box.add_widget(self.btn_vibe_ico)
        header_bar.add_widget(settings_box)
        main_layout.add_widget(header_bar)

        # Corps principal.
        body_layout = BoxLayout(
            orientation="horizontal", spacing=dp(12), size_hint_y=0.82
        )
        dashboard_panel = BoxLayout(
            orientation="vertical", spacing=dp(8), size_hint_x=0.42
        )

        card_metal = AestheticCard(
            orientation="vertical",
            padding=dp(8),
            size_hint_y=0.32,
            border_color="#334155",
        )
        self.lbl_metal_status = Label(
            text="[b][color=64748B]SOL NEUTRE[/color][/b]",
            font_size="18sp",
            markup=True,
            halign="center",
        )
        self.lbl_vdi_index = Label(
            text="INDICE VDI : 00",
            font_size="11sp",
            color=rgb("#94A3B8"),
        )
        card_metal.add_widget(self.lbl_metal_status)
        card_metal.add_widget(self.lbl_vdi_index)
        dashboard_panel.add_widget(card_metal)

        card_physic = AestheticCard(
            orientation="horizontal",
            padding=dp(10),
            size_hint_y=0.24,
            border_color="#0284C7",
        )
        self.lbl_signal_val = Label(
            text="0020\n[color=94A3B8][size=10]SIGNAL (LSB)[/size][/color]",
            font_size="18sp",
            bold=True,
            color=rgb("#10B981"),
            markup=True,
        )
        self.lbl_depth_val = Label(
            text="-- cm\n[color=94A3B8][size=10]PROFONDEUR NON MESURÉE[/size][/color]",
            font_size="16sp",
            bold=True,
            color=rgb("#F59E0B"),
            markup=True,
        )
        card_physic.add_widget(self.lbl_signal_val)
        card_physic.add_widget(self.lbl_depth_val)
        dashboard_panel.add_widget(card_physic)

        card_geology = AestheticCard(
            orientation="vertical",
            padding=dp(10),
            spacing=dp(4),
            size_hint_y=0.44,
            border_color="#1E293B",
        )
        box_water = BoxLayout(orientation="horizontal", size_hint_y=0.25)
        self.lbl_water_metrics = Label(
            text="SOL / EAU : non mesuré",
            font_size="10sp",
            color=rgb("#E2E8F0"),
            size_hint_x=0.5,
        )
        self.bar_water = ProgressBar(max=100, value=0, size_hint_x=0.5)
        box_water.add_widget(self.lbl_water_metrics)
        box_water.add_widget(self.bar_water)
        card_geology.add_widget(box_water)

        self.lbl_temp_metrics = Label(
            text="TEMPÉRATURE : non mesurée",
            font_size="10sp",
            color=rgb("#E2E8F0"),
            halign="left",
            size_hint_y=0.25,
        )
        card_geology.add_widget(self.lbl_temp_metrics)

        box_noise = BoxLayout(orientation="horizontal", size_hint_y=0.25)
        self.lbl_noise_metrics = Label(
            text="BRUIT : non mesuré",
            font_size="10sp",
            color=rgb("#E2E8F0"),
            size_hint_x=0.5,
        )
        self.bar_noise = ProgressBar(max=100, value=0, size_hint_x=0.5)
        box_noise.add_widget(self.lbl_noise_metrics)
        box_noise.add_widget(self.bar_noise)
        card_geology.add_widget(box_noise)

        self.lbl_hardware_telemetry = Label(
            text="BOBINE : non vérifiée | SEUIL : 40 LSB (simulation)",
            font_size="9sp",
            color=rgb("#94A3B8"),
            size_hint_y=0.25,
        )
        card_geology.add_widget(self.lbl_hardware_telemetry)
        dashboard_panel.add_widget(card_geology)
        body_layout.add_widget(dashboard_panel)

        self.matrix_view = MatrixScanner(size_hint_x=0.58)
        body_layout.add_widget(self.matrix_view)
        main_layout.add_widget(body_layout)

        self.card_notification = AestheticCard(
            padding=dp(6),
            size_hint_y=0.10,
            bg_color="#1E293B",
            border_color="#334155",
        )
        self.lbl_notification_text = Label(
            text="[color=38BDF8]INFO :[/color] Démarrage du système.",
            font_size="11sp",
            markup=True,
            halign="center",
        )
        self.card_notification.add_widget(self.lbl_notification_text)
        main_layout.add_widget(self.card_notification)

        Clock.schedule_once(self._start_logger, 0)
        Clock.schedule_interval(self.update_telemetry, 0.1)
        return main_layout

    def _update_background(self, widget, _value):
        self.bg_window.pos = widget.pos
        self.bg_window.size = widget.size

    def _start_logger(self, _dt):
        try:
            folder = Path(self.user_data_dir)
            folder.mkdir(parents=True, exist_ok=True)
            self.log_path = folder / (
                "georadar_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".csv"
            )
            with self.log_path.open("w", newline="", encoding="utf-8") as file:
                writer = __import__("csv").writer(file)
                writer.writerow([
                    "timestamp", "grid_x", "grid_y", "signal",
                    "metal_label", "mode"
                ])
        except OSError as exc:
            self.lbl_notification_text.text = (
                f"[color=EF4444]Erreur d'enregistrement CSV : {exc}[/color]"
            )

    def switch_hardware_alert(self, mode):
        self.smartphone_mode = mode
        if mode == "SONORE":
            self.btn_sound_ico.background_color = rgb("#10B981")
            self.btn_vibe_ico.background_color = rgb("#1E293B")
        else:
            self.btn_sound_ico.background_color = rgb("#1E293B")
            self.btn_vibe_ico.background_color = rgb("#F59E0B")

    def connect_android_bluetooth(self, device_name):
        """Connexion RFCOMM au HC-05 déjà appairé (Android uniquement)."""
        try:
            from jnius import autoclass

            BluetoothAdapter = autoclass("android.bluetooth.BluetoothAdapter")
            UUID = autoclass("java.util.UUID")
            adapter = BluetoothAdapter.getDefaultAdapter()
            if adapter is None or not adapter.isEnabled():
                self._set_notice("Bluetooth désactivé ou indisponible.")
                return None

            bonded = adapter.getBondedDevices().toArray()
            for device in bonded:
                if str(device.getName()) == device_name:
                    serial_uuid = UUID.fromString(
                        "00001101-0000-1000-8000-00805F9B34FB"
                    )
                    sock = device.createRfcommSocketToServiceRecord(serial_uuid)
                    sock.connect()
                    self.bluetooth_socket = sock
                    self._set_notice("HC-05 connecté.")
                    return sock.getInputStream()

            self._set_notice("HC-05 non appairé : connexion Bluetooth inactive.")
        except Exception as exc:
            self._set_notice(f"Bluetooth indisponible : {exc}")
        return None

    def _set_notice(self, message):
        if hasattr(self, "lbl_notification_text"):
            self.lbl_notification_text.text = message

    def trigger_smartphone_hardware(self):
        if self.smartphone_mode == "VIBREUR" and vibrator is not None:
            try:
                vibrator.vibrate(time=0.2)
            except Exception:
                pass
        elif self.smartphone_mode == "SONORE" and self.detect_sound:
            try:
                self.detect_sound.stop()
                self.detect_sound.play()
            except Exception:
                pass

    def _read_bluetooth_packet(self):
        """Lit des lignes au format $PI_DATA,signal,depth,label,seuil,pulse."""
        if self.android_stream is None:
            return None

        try:
            available = self.android_stream.available()
            if available <= 0:
                return None

            buffer = bytearray(available)
            count = self.android_stream.read(buffer)
            if count <= 0:
                return None

            self.rx_buffer += bytes(buffer[:count]).decode(
                "utf-8", errors="ignore"
            )
            if "\n" not in self.rx_buffer:
                return None

            lines = self.rx_buffer.split("\n")
            self.rx_buffer = lines[-1]

            for line in lines[:-1]:
                line = line.strip()
                if not line.startswith("$PI_DATA,"):
                    continue

                tokens = line.split(",")
                if len(tokens) < 6:
                    continue

                signal = int(tokens[1])
                depth = int(tokens[2])
                metal = tokens[3].strip()
                sensitivity = int(tokens[4])
                pulse = int(tokens[5])
                return signal, depth, metal, sensitivity, pulse

        except Exception as exc:
            self._set_notice(f"Erreur lecture Bluetooth : {exc}")
        return None

    def _write_csv(self, signal, metal, mode):
        if self.log_path is None:
            return
        try:
            with self.log_path.open("a", newline="", encoding="utf-8") as file:
                writer = __import__("csv").writer(file)
                writer.writerow([
                    datetime.now().isoformat(timespec="milliseconds"),
                    self.cur_x,
                    self.cur_y,
                    signal,
                    metal,
                    mode,
                ])
        except OSError:
            pass

    def update_telemetry(self, _dt):
        packet = self._read_bluetooth_packet()

        if packet is not None:
            signal, depth, metal, sensitivity, pulse = packet
            mode = "BLUETOOTH"
            depth_text = f"{depth} cm (valeur STM32)"
            self.lbl_water_metrics.text = "SOL / EAU : non connecté"
            self.lbl_temp_metrics.text = "TEMPÉRATURE : non connectée"
            self.lbl_noise_metrics.text = "BRUIT : non mesuré"
            self.bar_water.value = 0
            self.bar_noise.value = 0
        else:
            # Simulation d'interface seulement : aucune mesure physique.
            signal = random.randint(50, 2200) if random.random() > 0.92 else 18
            sensitivity = 40
            pulse = 150
            metal = "GOLD/COPPER" if signal > 950 else (
                "IRON/FERROUS" if signal >= sensitivity else "NONE"
            )
            depth = 0
            depth_text = "-- cm (non mesurée)"
            mode = "SIMULATION"
            self.lbl_water_metrics.text = "SOL / EAU : non mesuré"
            self.lbl_temp_metrics.text = "TEMPÉRATURE : non mesurée"
            self.lbl_noise_metrics.text = "BRUIT : non mesuré"
            self.bar_water.value = 0
            self.bar_noise.value = 0

        vdi = int((signal / 4096.0) * 99) if signal > sensitivity else 0
        self.lbl_vdi_index.text = f"INDICE VDI : {vdi:02d}"
        self.lbl_signal_val.text = (
            f"{signal}\n[color=94A3B8][size=10]SIGNAL ({mode})[/size][/color]"
        )
        self.lbl_depth_val.text = (
            f"{depth_text}\n[color=94A3B8][size=10]PROFONDEUR[/size][/color]"
        )
        self.lbl_hardware_telemetry.text = (
            f"BOBINE : non vérifiée | SEUIL : {sensitivity} LSB | "
            f"IMPULSION : {pulse} µs"
        )

        alert = signal > sensitivity
        if alert and metal == "GOLD/COPPER":
            self.lbl_metal_status.text = (
                "[b][color=F59E0B]SIGNAL ÉLEVÉ[/color][/b]"
            )
            notice = "Signal élevé : classe non confirmée."
            self.card_notification.border_color = "#F59E0B"
        elif alert and metal == "IRON/FERROUS":
            self.lbl_metal_status.text = (
                "[b][color=EF4444]SIGNAL DÉTECTÉ[/color][/b]"
            )
            notice = "Signal détecté : nature du métal non confirmée."
            self.card_notification.border_color = "#EF4444"
        elif metal == "VOID":
            self.lbl_metal_status.text = (
                "[b][color=3B82F6]ANOMALIE[/color][/b]"
            )
            notice = "Anomalie signalée par la trame ; cavité non confirmée."
            self.card_notification.border_color = "#3B82F6"
        else:
            self.lbl_metal_status.text = (
                "[b][color=64748B]SIGNAL FAIBLE[/color][/b]"
            )
            notice = "Signal faible ou sol neutre."
            self.card_notification.border_color = "#334155"

        self.lbl_notification_text.text = (
            f"[color=38BDF8]{mode} :[/color] {notice}"
        )

        if alert and self.last_alert_state != (mode, metal):
            self.trigger_smartphone_hardware()
        self.last_alert_state = (mode, metal) if alert else None

        self.matrix_view.update_voxel(self.cur_x, self.cur_y, signal, metal)
        self._write_csv(signal, metal, mode)

        self.cur_y += 1
        if self.cur_y >= 12:
            self.cur_y = 0
            self.cur_x = (self.cur_x + 1) % 12

    def on_stop(self):
        try:
            if self.bluetooth_socket is not None:
                self.bluetooth_socket.close()
        except Exception:
            pass


if __name__ == "__main__":
    UnifiedGeoradarApp().run()
