import uuid
import webbrowser
import requests
import time
import threading
import tkinter as tk
import win32gui
import win32api
from spotipy import Spotify
from PIL import Image, ImageTk
import os
import sys
import win32event
import winerror
import json

# === CONFIGURACIÓN ===
BACKEND_BASE = 'https://spoty-tb.brianmartinezsebas.com.ar'
SESSION_FILE = os.path.join(os.getenv("APPDATA"), "spoty-tb-session.json")

# === SINGLE INSTANCE ===
mutex = win32event.CreateMutex(None, False, "Spoty-TB-SingleInstanceMutex")
if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
    import ctypes
    ctypes.windll.user32.MessageBoxW(0, "Spoty-TB ya se está ejecutando.", "Instancia detectada", 0x40 | 0x1)
    sys.exit(0)

# === FUNCIONES DE SESIÓN ===
def save_session(tokens):
    with open(SESSION_FILE, "w") as f:
        json.dump(tokens, f)

def load_session():
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r") as f:
            return json.load(f)
    return None

def clear_session():
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)

# === FUNCIONES DE AUTENTICACIÓN BACKEND ===
def get_auth_url_and_state():
    resp = requests.get(f"{BACKEND_BASE}/auth_url.php")
    resp.raise_for_status()
    data = resp.json()
    return data["auth_url"], data["state"]

def wait_for_tokens_backend(state):
    print("Esperando tokens desde backend...")
    for _ in range(60):
        try:
            r = requests.get(f"{BACKEND_BASE}/get_tokens.php", params={'state': state})
            if r.status_code == 200:
                tokens = r.json()
                if "access_token" in tokens:
                    return tokens
        except Exception as e:
            print("Error:", e)
        time.sleep(2)
    raise Exception("No se recibieron los tokens en el tiempo esperado")

def refresh_access_token_backend(state):
    r = requests.get(f"{BACKEND_BASE}/refresh_token.php", params={"state": state})
    r.raise_for_status()
    return r.json()

# === CONTROLADOR SPOTIFY ===
class SpotifyController:
    def __init__(self, access_token, refresh_token, state):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.state = state
        self.sp = Spotify(auth=self.access_token)

    def refresh_if_needed(self):
        try:
            self.sp.current_playback()
        except:
            print("Token expirado. Refrescando...")
            new_tokens = refresh_access_token_backend(self.state)
            self.access_token = new_tokens["access_token"]
            self.sp = Spotify(auth=self.access_token)
            # Guardar el nuevo token actualizado en sesión
            save_session({
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "state": self.state
            })

    def get_current_track(self):
        self.refresh_if_needed()
        current = self.sp.current_playback()
        if current and current["is_playing"]:
            item = current["item"]
            return f"{item['name']} - {item['artists'][0]['name']}"
        elif current:
            return f"En pausa: {current['item']['name']}"
        else:
            return "Spotify inactivo"

    def play(self):
        self.refresh_if_needed()
        self.sp.start_playback()

    def pause(self):
        self.refresh_if_needed()
        self.sp.pause_playback()

    def next(self):
        self.refresh_if_needed()
        self.sp.next_track()

    def previous(self):
        self.refresh_if_needed()
        self.sp.previous_track()

# === FUNCIONES DE UI ===
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_notification_area_rect():
    taskbar = win32gui.FindWindow("Shell_TrayWnd", None)
    notify = win32gui.FindWindowEx(taskbar, 0, "TrayNotifyWnd", None)
    syspager = win32gui.FindWindowEx(notify, 0, "SysPager", None)
    toolbar = win32gui.FindWindowEx(syspager, 0, "ToolbarWindow32", None)
    rect = win32gui.GetWindowRect(toolbar)
    return rect

def convert_black_to_white(img):
    img = img.convert("RGBA")
    datas = img.getdata()
    new_data = []
    for item in datas:
        if item[0] < 50 and item[1] < 50 and item[2] < 50:
            new_data.append((255, 255, 255, item[3]))
        else:
            new_data.append(item)
    img.putdata(new_data)
    return img

def truncate_text(text, max_length=40):
    if len(text) > max_length:
        return text[:max_length - 3] + "..."
    return text

def create_spotify_widget():
    root = tk.Tk()
    root.overrideredirect(True)
    def keep_on_top():
        root.attributes("-topmost", True)
        root.after(1000, keep_on_top)
    keep_on_top()
    root.configure(bg="white")

    screen_width = win32api.GetSystemMetrics(0)
    screen_height = win32api.GetSystemMetrics(1)

    left, top, right, bottom = get_notification_area_rect()
    width = 450
    height = bottom - top

    x = left - width - 50
    y = top

    root.geometry(f"{width}x{height}+{x}+{y}")

    frame = tk.Frame(root, bg="white")
    frame.pack(expand=True, fill="both")

    pixeles_img = 18
    img_prev = Image.open(resource_path("assets/prev.png")).resize((pixeles_img, pixeles_img), Image.LANCZOS)
    img_prev = convert_black_to_white(img_prev)
    img_pause = Image.open(resource_path("assets/pause.png")).resize((pixeles_img, pixeles_img), Image.LANCZOS)
    img_pause = convert_black_to_white(img_pause)
    img_play = Image.open(resource_path("assets/play.png")).resize((pixeles_img, pixeles_img), Image.LANCZOS)
    img_play = convert_black_to_white(img_play)
    img_next = Image.open(resource_path("assets/next.png")).resize((pixeles_img, pixeles_img), Image.LANCZOS)
    img_next = convert_black_to_white(img_next)
    img_exit = Image.open(resource_path("assets/exit.png")).resize((pixeles_img, pixeles_img), Image.LANCZOS)
    img_exit = convert_black_to_white(img_exit)
    icon_prev = ImageTk.PhotoImage(img_prev)
    icon_pause = ImageTk.PhotoImage(img_pause)
    icon_play = ImageTk.PhotoImage(img_play)
    icon_next = ImageTk.PhotoImage(img_next)
    icon_exit = ImageTk.PhotoImage(img_exit)

    title_label = tk.Label(frame, text="Cargando...", bg="#222222", fg="white", font=("Segoe UI Variable", 10, "bold"))
    title_label.pack(side="left", padx=(5, 5), pady=10, expand=True, fill="x")
    frame.configure(bg="#222222")
    root.configure(bg="#222222")

    pixeles_btn = 30
    btn_prev = tk.Button(frame, image=icon_prev, bg="#222222", bd=0, width=pixeles_btn, height=pixeles_btn, command=controller.previous)
    btn_play_pause = tk.Button(frame, image=icon_pause, bg="#222222", bd=0, width=pixeles_btn, height=pixeles_btn)
    btn_next = tk.Button(frame, image=icon_next, bg="#222222", bd=0, width=pixeles_btn, height=pixeles_btn, command=controller.next)
    btn_quit = tk.Button(frame, image=icon_exit, bg="#222222", bd=0, width=pixeles_btn, height=pixeles_btn, command=root.destroy)

    espacio = 7
    btn_prev.pack(side="left", padx=espacio, pady=espacio)
    btn_play_pause.pack(side="left", padx=espacio, pady=espacio)
    btn_next.pack(side="left", padx=espacio, pady=espacio)
    btn_quit.pack(side="left", padx=espacio, pady=espacio)

    def update_ui():
        while True:
            try:
                current = controller.sp.current_playback()
                if current and current["is_playing"]:
                    btn_play_pause.config(image=icon_pause)
                    full_title = f"{current['item']['name']} - {current['item']['artists'][0]['name']}"
                    title = truncate_text(full_title, 32)
                elif current and current["item"]:
                    btn_play_pause.config(image=icon_play)
                    full_title = f"En pausa: {current['item']['name']}"
                    title = truncate_text(full_title, 32)
                else:
                    btn_play_pause.config(image=icon_play)
                    title = "Spotify inactivo"

                title_label.config(text=title)
            except Exception as e:
                title_label.config(text="Error al obtener estado")
                btn_play_pause.config(image=icon_play)
            time.sleep(3)

    def toggle_play_pause():
        try:
            current = controller.sp.current_playback()
            if current and current["is_playing"]:
                controller.pause()
            else:
                controller.play()
        except:
            pass

    btn_play_pause.config(command=toggle_play_pause)

    threading.Thread(target=update_ui, daemon=True).start()

    root.mainloop()

# === MAIN ===
tokens = load_session()
state = None

if tokens is None or "state" not in tokens:
    auth_url, state = get_auth_url_and_state()
    print("Abriendo navegador para autenticación...")
    webbrowser.open(auth_url)
    tokens = wait_for_tokens_backend(state)
    print("Tokens recibidos:", tokens)
    tokens["state"] = state  # Guardamos el state para refresco
    save_session(tokens)
else:
    print("Sesión cargada desde archivo.")
    state = tokens.get("state")

try:
    controller = SpotifyController(tokens["access_token"], tokens["refresh_token"], state)
    controller.refresh_if_needed()
except Exception as e:
    print("Error con los tokens, limpiando sesión y pidiendo login otra vez.")
    clear_session()
    sys.exit(1)

create_spotify_widget()
