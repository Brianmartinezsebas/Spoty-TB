import uuid
import webbrowser
import requests
import time
import threading
import tkinter as tk
import win32gui
import win32api
from spotipy import Spotify
from PIL import Image, ImageTk, ImageDraw
import os
import sys
import win32event
import winerror
import json
import io
from flask import Flask, request
from urllib.parse import urlencode

# === CONFIGURACIÓN LOCAL ===
REDIRECT_URI = "http://127.0.0.1:8888/callback"
TOKEN_FILE = os.path.join(os.getenv("APPDATA"), "spoty-tb-session.json")
CREDENTIALS_FILE = os.path.join(os.getenv("APPDATA"), "spoty-tb-credentials.json")

client_id = None
client_secret = None

# === SINGLE INSTANCE ===
mutex = win32event.CreateMutex(None, False, "Spoty-TB-SingleInstanceMutex")
if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
    import ctypes
    ctypes.windll.user32.MessageBoxW(0, "Spoty-TB ya se está ejecutando.", "Instancia detectada", 0x40 | 0x1)
    sys.exit(0)

modal_open = False  # <-- agrega esto al inicio del archivo (fuera de cualquier función)

# === UI para pedir Client ID/Secret ===
def prompt_client_credentials(force=False, error_msg=None, button_to_disable=None):
    global client_id, client_secret, modal_open
    if modal_open:
        return
    modal_open = True
    if button_to_disable:
        button_to_disable.config(state="disabled")
    prev_id, prev_secret = None, None
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE) as f:
            data = json.load(f)
            prev_id = data.get("client_id", "")
            prev_secret = data.get("client_secret", "")

    if not prev_id or not prev_secret or force:
        while True:
            modal_open = True  # Marca que el modal está abierto
            root = tk.Tk()
            root.title("Credenciales de Spotify")
            root.geometry("420x340")
            root.resizable(False, False)
            root.configure(bg="#222222")

            # Centrar ventana en pantalla
            root.update_idletasks()
            w = 420
            h = 350
            x = (root.winfo_screenwidth() // 2) - (w // 2)
            y = (root.winfo_screenheight() // 2) - (h // 2)
            root.geometry(f"{w}x{h}+{x}+{y}")

            # Link a Spotify Developers
            def open_spotify_dashboard(event):
                webbrowser.open_new("https://developer.spotify.com/dashboard")

            link_label = tk.Label(
                root, text="Ir a Spotify Developers", fg="#1DB954", bg="#222222",
                font=("Segoe UI", 10, "underline"), cursor="hand2"
            )
            link_label.pack(padx=18, pady=(12, 2), anchor="w")
            link_label.bind("<Button-1>", open_spotify_dashboard)

            # Tutorial
            tutorial = (
                "1. Haz clic en el enlace de arriba para abrir Spotify Developers\n"
                "2. Haz clic en 'Create an App'\n"
                "3. Copia el Client ID y Client Secret aquí\n"
                "4. En 'Redirect URIs' agrega:"
            )
            tk.Label(
                root, text="¿Cómo obtener tus credenciales de Spotify?",
                bg="#222222", fg="#1DB954", font=("Segoe UI", 10, "bold")
            ).pack(pady=(0, 2), anchor="w", padx=18)
            tk.Label(
                root, text=tutorial, bg="#222222", fg="#bbbbbb",
                font=("Segoe UI", 9), justify="left", anchor="w"
            ).pack(padx=18, pady=(0, 2), anchor="w")

            # Entry para copiar el redirect URI
            redirect_entry = tk.Entry(
                root, width=38, font=("Segoe UI", 9), bg="#333333", fg="#1DB954",
                relief="flat", readonlybackground="#333333"
            )
            redirect_entry.insert(0, "http://127.0.0.1:8888/callback")
            redirect_entry.config(state="readonly")
            redirect_entry.pack(padx=18, pady=(0, 10), anchor="w")

            # Mostrar error si existe
            if error_msg:
                tk.Label(
                    root, text=error_msg, bg="#222222", fg="red",
                    font=("Segoe UI", 9, "bold"), wraplength=380, justify="left"
                ).pack(padx=18, pady=(0, 10), anchor="w")

            # Inputs
            tk.Label(root, text="Client ID:", bg="#222222", fg="white", font=("Segoe UI", 10)).pack(pady=(5, 0), anchor="w", padx=18)
            entry_id = tk.Entry(root, width=44, bg="#333333", fg="white", insertbackground="white", relief="flat", font=("Segoe UI", 10))
            entry_id.pack(padx=18, anchor="w")
            if prev_id:
                entry_id.insert(0, prev_id)

            tk.Label(root, text="Client Secret:", bg="#222222", fg="white", font=("Segoe UI", 10)).pack(pady=(10, 0), anchor="w", padx=18)
            entry_secret = tk.Entry(root, width=44, show="*", bg="#333333", fg="white", insertbackground="white", relief="flat", font=("Segoe UI", 10))
            entry_secret.pack(padx=18, anchor="w")
            if prev_secret:
                entry_secret.insert(0, prev_secret)

            error_label = tk.Label(root, text="", bg="#222222", fg="red", font=("Segoe UI", 9, "bold"))
            error_label.pack(pady=(5, 0))

            def guardar_y_cerrar():
                nonlocal entry_id, entry_secret
                cid = entry_id.get().strip()
                csecret = entry_secret.get().strip()
                if cid and csecret:
                    global client_id, client_secret, modal_open
                    client_id = cid
                    client_secret = csecret
                    with open(CREDENTIALS_FILE, "w") as f:
                        json.dump({"client_id": cid, "client_secret": csecret}, f)
                    modal_open = False
                    if button_to_disable:
                        button_to_disable.config(state="normal")
                    root.destroy()
                else:
                    error_label.config(text="Debes ingresar ambos campos.")

            def on_close():
                global modal_open
                modal_open = False
                if button_to_disable:
                    button_to_disable.config(state="normal")
                root.destroy()

            root.protocol("WM_DELETE_WINDOW", on_close)

            tk.Button(
                root, text="Guardar y continuar", command=guardar_y_cerrar,
                bg="#1DB954", fg="white", font=("Segoe UI", 10, "bold"), relief="flat", activebackground="#1ed760"
            ).pack(pady=18)

            root.mainloop()
            modal_open = False  # Por si sale del loop por cualquier razón

            if client_id and client_secret:
                break
    else:
        client_id = prev_id
        client_secret = prev_secret

# === Servidor local Flask para capturar redirect ===
def start_auth_server(code_holder):
    app = Flask(__name__)

    @app.route("/callback")
    def callback():
        code = request.args.get("code")
        if code:
            code_holder["code"] = code
            return "<h1>✅ Autenticación completada</h1><p>Podés cerrar esta ventana.</p>"
        else:
            return "<h1>❌ Error</h1><p>No se recibió ningún código.</p>"

    def run():
        app.run(port=8888, use_reloader=False)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

# === Flujo OAuth ===
def build_auth_url():
    scope = "user-read-playback-state user-modify-playback-state user-library-read user-library-modify"
    params = {
        "response_type": "code",
        "client_id": client_id,
        "scope": scope,
        "redirect_uri": REDIRECT_URI,
        "show_dialog": "true",
        "state": "spoty123"
    }
    return "https://accounts.spotify.com/authorize?" + urlencode(params)

def exchange_code_for_token(code):
    # print("DEBUG: client_id =", client_id)
    # print("DEBUG: client_secret =", client_secret)
    # print("DEBUG: redirect_uri =", REDIRECT_URI)
    # print("DEBUG: code =", code)
    url = "https://accounts.spotify.com/api/token"
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": client_id,
        "client_secret": client_secret
    }
    response = requests.post(url, data=data)
    if response.status_code != 200:
        print("ERROR:", response.status_code, response.text)
    response.raise_for_status()
    return response.json()

def save_tokens(tokens):
    with open(TOKEN_FILE, "w") as f:
        json.dump(tokens, f, indent=2)
    print("✅ Tokens guardados en:", TOKEN_FILE)

def load_tokens():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            return json.load(f)
    return None

def load_credentials():
    global client_id, client_secret
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE) as f:
            data = json.load(f)
            client_id = data.get("client_id")
            client_secret = data.get("client_secret")

def clear_session():
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)

# === CONTROLADOR SPOTIFY ===
class SpotifyController:
    def __init__(self, access_token, refresh_token=None, state=None):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.state = state
        self.sp = Spotify(auth=self.access_token)

    def refresh_token(refresh_token):
        url = "https://accounts.spotify.com/api/token"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        response = requests.post(url, data=data)
        response.raise_for_status()
        tokens = response.json()
        tokens["refresh_token"] = tokens.get("refresh_token", refresh_token)  # puede venir vacío
        save_tokens(tokens)
        return tokens

    def refresh_if_needed(self):
        try:
            self.sp.current_playback()
        except Exception as e:
            if hasattr(e, 'http_status') and e.http_status == 401:
                print("Token expirado. Refrescando token...")
                if self.refresh_token:
                    tokens = SpotifyController.refresh_token(self.refresh_token)
                    self.access_token = tokens["access_token"]
                    self.refresh_token = tokens.get("refresh_token", self.refresh_token)
                    self.sp = Spotify(auth=self.access_token)
                else:
                    print("No hay refresh_token disponible. Reinicia la app para reautenticar.")
                    clear_session()
                    sys.exit(1)
            else:
                raise

    def safe_api_call(self, func, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if hasattr(e, 'http_status') and e.http_status == 401:
                self.refresh_if_needed()
                return func(*args, **kwargs)
            else:
                raise

    def get_current_track(self):
        return self.safe_api_call(self.sp.current_playback)

    def play(self):
        self.safe_api_call(self.sp.start_playback)

    def pause(self):
        self.safe_api_call(self.sp.pause_playback)

    def next(self):
        self.safe_api_call(self.sp.next_track)

    def previous(self):
        self.safe_api_call(self.sp.previous_track)

def auto_refresh_loop(controller):
    def loop():
        while True:
            time.sleep(60 * 50)  # refresca cada 50 minutos
            try:
                controller.refresh_if_needed()
            except Exception as e:
                print("Error al refrescar token en background:", e)
    threading.Thread(target=loop, daemon=True).start()

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

def rounded_image(img, radius):
    img = img.convert("RGBA")
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, img.size[0], img.size[1]], radius=radius, fill=255)
    img.putalpha(mask)
    return img

def truncate_text(text, max_length=40):
    if len(text) > max_length:
        return text[:max_length - 3] + "..."
    return text

def create_spotify_widget(controller):
    root = tk.Tk()
    root.overrideredirect(True)
    def keep_on_top():
        root.attributes("-topmost", True)
        root.after(100, keep_on_top)
    keep_on_top()
    root.configure(bg="white")

    screen_width = win32api.GetSystemMetrics(0)
    screen_height = win32api.GetSystemMetrics(1)

    left, top, right, bottom = get_notification_area_rect()
    width = 450  # Ancho fijo del widget
    height = bottom - top
    
    x = left - width - 50
    y = top

    root.geometry(f"{width}x{height}+{x}+{y}")

    frame = tk.Frame(root, bg="white")
    frame.pack(expand=True, fill="both")

    # Frame para títulos
    title_frame = tk.Frame(frame, bg="#222222")
    title_frame.pack(side="left", fill="x" )

    # Frame para los botones
    controls_frame = tk.Frame(frame, bg="#222222")
    controls_frame.pack(side="right")

    pixeles_img = 16
    pixeles_btn = 25
    espacio = 7
    icon_names = [
        ("prev", "prev.png"),
        ("pause", "pause.png"),
        ("play", "play.png"),
        ("next", "next.png"),
        ("exit", "exit.png"),
        ("expand", "arrow.png"),
        ("vol", "vol.png"),
        ("logout", "logout.png"),
    ]
    icons = {}
    for name, filename in icon_names:
        img = Image.open(resource_path(f"assets/{filename}")).resize((pixeles_img, pixeles_img), Image.LANCZOS)
        img = convert_black_to_white(img)
        icons[name] = ImageTk.PhotoImage(img)
    # Caso especial para collapse (expand rotado)
    img_collapse = Image.open(resource_path("assets/arrow.png")).resize((pixeles_img, pixeles_img), Image.LANCZOS)
    img_collapse = convert_black_to_white(img_collapse).rotate(180)
    icons["collapse"] = ImageTk.PhotoImage(img_collapse)

    icon_heart_empty = ImageTk.PhotoImage(
        convert_black_to_white(
            Image.open(resource_path("assets/heart_empty.png")).resize((pixeles_img, pixeles_img), Image.LANCZOS)
        )
    )
    icon_heart_filled = ImageTk.PhotoImage(
        convert_black_to_white(
            Image.open(resource_path("assets/heart_filled.png")).resize((pixeles_img, pixeles_img), Image.LANCZOS)
        )
    )

    icon_prev = icons["prev"]
    icon_pause = icons["pause"]
    icon_play = icons["play"]
    icon_next = icons["next"]
    icon_exit = icons["exit"]
    icon_expand = icons["expand"]
    icon_collapse = icons["collapse"]
    icon_vol = icons["vol"]
    icon_logout = icons["logout"]

    # Imagen del álbum para modo compacto
    album_img_label_compact = tk.Label(title_frame, bg="#222222")
    album_img_label_compact.pack(side="left", padx=(7, 2), pady=3)
    
    # Título y artista para modo compacto
    title_label_compact = tk.Label(title_frame, text="Cargando...", bg="#222222", fg="white", font=("CircularStd-Book", 9), anchor="w")
    artist_label_compact = tk.Label(title_frame, text="", bg="#222222", fg="#bbbbbb", font=("CircularStd-Book", 8), anchor="w")

    title_label_compact.pack(side="top", anchor="w", padx=0, pady=0, fill="x")
    artist_label_compact.pack(side="top", anchor="w", padx=0, pady=0, fill="x")


    # Título y autores para modo expandido (centrados debajo de la imagen)
    title_label_expanded = tk.Label(root, text="Cargando...", bg="#222222", fg="white", font=("Segoe UI Variable", 12, "bold"))
    artist_label_expanded = tk.Label(root, text="", bg="#222222", fg="#bbbbbb", font=("Segoe UI Variable", 10))

    frame.configure(bg="#222222")
    root.configure(bg="#222222")

    pixeles_btn = 25
    btn_heart = tk.Button(controls_frame, image=icon_heart_empty, bg="#222222", bd=0, width=pixeles_btn, height=pixeles_btn)
    btn_heart.pack(side="left", padx=1, pady=espacio)
    btn_vol = tk.Button(controls_frame, image=icon_vol, bg="#222222", bd=0, width=pixeles_btn, height=pixeles_btn)
    btn_prev = tk.Button(controls_frame, image=icon_prev, bg="#222222", bd=0, width=pixeles_btn, height=pixeles_btn, command=controller.previous)
    btn_play_pause = tk.Button(controls_frame, image=icon_pause, bg="#222222", bd=0, width=pixeles_btn, height=pixeles_btn)
    btn_next = tk.Button(controls_frame, image=icon_next, bg="#222222", bd=0, width=pixeles_btn, height=pixeles_btn, command=controller.next)
    btn_expand = tk.Button(controls_frame, image=icon_expand, bg="#222222", bd=0, width=pixeles_btn, height=pixeles_btn)
    btn_collapse = tk.Button(root, image=icon_collapse, bg="#222222", bd=0, width=pixeles_btn, height=pixeles_btn)
    btn_exit = tk.Button(root, image=icon_exit, bg="#222222", bd=0, width=pixeles_btn, height=pixeles_btn, command=root.destroy)
    btn_exit.place_forget()  # Oculto al inicio
    btn_collapse.place_forget()  # Oculto al inicio
    btn_logout = tk.Button(root, image=icon_logout, bg="#222222", bd=0, width=pixeles_btn, height=pixeles_btn, command=lambda: logout())
    btn_logout.place_forget()

    # Botón para editar credenciales
    btn_edit_creds = tk.Button(
        root, text="Editar credenciales", bg="#333333", fg="#1DB954",
        font=("Segoe UI", 9, "bold"), relief="flat", activebackground="#444444",
        command=lambda: edit_credentials()
    )
    btn_edit_creds.place_forget()

    def edit_credentials():
        prompt_client_credentials(force=True, button_to_disable=btn_edit_creds)
        python = sys.executable
        os.execl(python, python, *sys.argv)

    def logout():
        clear_session()
        root.destroy()
        sys.exit(0)

    # Empaquetado inicial (compacto)
    btn_heart.pack(side="left", padx=1, pady=espacio)
    btn_vol.pack(side="left", padx=1, pady=espacio)
    btn_prev.pack(side="left", padx=1, pady=espacio)
    btn_play_pause.pack(side="left", padx=1, pady=espacio)
    btn_next.pack(side="left", padx=1, pady=espacio)
    btn_expand.pack(side="left", padx=1, pady=espacio)

    # Variables para el estado
    is_expanded = False
    expanded_height = 350  # Altura expandida
    collapsed_height = height

    # Elementos extra (ocultos al inicio)
    album_img_label = tk.Label(root, bg="#222222")
    precached_album_img = None  # Para precargar la imagen

    # Barra de progreso tipo Spotify
    BAR_WIDTH = width - 180
    BAR_HEIGHT = 6
    THUMB_RADIUS = 8
    progress_canvas = tk.Canvas(root, width=BAR_WIDTH, height=THUMB_RADIUS*2, bg="#222222", highlightthickness=0, bd=0)
    progress_canvas.place_forget()

    # Labels para el tiempo
    label_time_current = tk.Label(root, text="0:00", bg="#222222", fg="white", font=("Segoe UI Variable", 9))
    label_time_total = tk.Label(root, text="0:00", bg="#222222", fg="white", font=("Segoe UI Variable", 9))
    label_time_current.place_forget()
    label_time_total.place_forget()

    def draw_progress_bar(current_sec, total_sec):
        progress_canvas.delete("all")
        # Fondo de la barra
        progress_canvas.create_rectangle(
            0, (THUMB_RADIUS-BAR_HEIGHT//2), BAR_WIDTH, (THUMB_RADIUS+BAR_HEIGHT//2),
            fill="#444444", outline=""
        )
        # Barra de progreso
        if total_sec > 0:
            filled = int(BAR_WIDTH * current_sec / total_sec)
        else:
            filled = 0
        progress_canvas.create_rectangle(
            0, (THUMB_RADIUS-BAR_HEIGHT//2), filled, (THUMB_RADIUS+BAR_HEIGHT//2),
            fill="#1DB954", outline=""
        )
        # Thumb (círculo)
        progress_canvas.create_oval(
            filled-THUMB_RADIUS, 0, filled+THUMB_RADIUS, THUMB_RADIUS*2,
            fill="#1DB954", outline="#1DB954"
        )

    # --- Animación rápida y fluida ---
    animation_duration = 200  # ms
    animation_steps = 30
    animation_interval = animation_duration // animation_steps
    delta = max(1, (expanded_height - collapsed_height) // animation_steps)
    ALBUM_IMG_SIZE = 130
    def animate_expand():
        current_height = root.winfo_height()
        if current_height < expanded_height:
            new_height = min(current_height + delta, expanded_height)
            new_y = y - (new_height - height)
            root.geometry(f"{width}x{new_height}+{x}+{new_y}")
            root.after(animation_interval, animate_expand)
        else:
            album_img_label.place(x=(width-ALBUM_IMG_SIZE)//2, y=50)
            album_img_label_compact.pack_forget()
            title_label_compact.pack_forget()
            artist_label_compact.pack_forget()
            title_label_expanded.place(x=0, y=20+ALBUM_IMG_SIZE+40, width=width, height=30)
            artist_label_expanded.place(x=0, y=10+ALBUM_IMG_SIZE+80, width=width, height=24)
            frame.pack_forget()
            controls_frame.pack_forget()
            # Centra los botones dentro del controls_frame
            for btn in [btn_prev, btn_play_pause, btn_next, btn_expand]:
                btn.pack_forget()
                btn.pack(side="left", pady=espacio, padx=1)
            frame.pack(expand=True, fill="both")
            frame.update_idletasks()  # Asegura que los tamaños estén actualizados
            controls_frame.update_idletasks()
            controls_width = controls_frame.winfo_reqwidth()
            controls_height = controls_frame.winfo_reqheight()
            controls_x = (width - controls_width + 40) // 2
            controls_y = expanded_height - controls_height - 15 # 30 píxeles de margen inferior
            controls_frame.place(in_=frame, x=controls_x, y=controls_y)
            progress_canvas.place(x=90, y=expanded_height-80)
            label_time_current.place(x=50, y=expanded_height-80+THUMB_RADIUS-10)
            label_time_total.place(x=90+BAR_WIDTH+10, y=expanded_height-80+THUMB_RADIUS-10)
            btn_expand.pack_forget()
            btn_vol.pack_forget()
            btn_exit.place(x=width-pixeles_btn-10, y=10)
            btn_collapse.place(x=width-2*pixeles_btn-20, y=10)
            btn_logout.place(x=10, y=10)
            btn_edit_creds.place(x=width//2-70, y=10, width=140, height=28)  # Centrado arriba

    def animate_collapse():
        current_height = root.winfo_height()
        if current_height > collapsed_height:
            new_height = max(current_height - delta, collapsed_height)
            new_y = y - (new_height - height)
            root.geometry(f"{width}x{new_height}+{x}+{new_y}")
            root.after(animation_interval, animate_collapse)
        else:
            album_img_label.place_forget()
            progress_canvas.place_forget()
            label_time_current.place_forget()
            label_time_total.place_forget()
            title_label_expanded.place_forget()
            # Vuelve a poner los labels y los botones en modo compacto
            title_label_compact.pack_forget()
            artist_label_compact.pack_forget()
            album_img_label_compact.pack(side="left", padx=(7, 2), pady=3)
            title_label_compact.pack(side="top", anchor="w", padx=0, pady=0, fill="x")
            artist_label_compact.pack(side="top", anchor="w", padx=0, pady=0, fill="x")
            frame.pack_forget()
            # Cambia el pack de controls_frame para poner los botones a la derecha
            controls_frame.pack_forget()
            controls_frame.pack(side="right")
            btn_vol.pack_forget()
            btn_vol.pack(side="left", padx=1, pady=espacio)
            for btn in [btn_prev, btn_play_pause, btn_next, btn_expand]:
                btn.pack_forget()
                btn.pack(side="left", padx=1, pady=espacio)
            frame.pack(expand=True, fill="both")
            btn_exit.place_forget()
            btn_collapse.place_forget()
            btn_logout.place_forget()
            btn_edit_creds.place_forget()

    def toggle_expand():
        nonlocal is_expanded
        is_expanded = not is_expanded
        if is_expanded:
            animate_expand()
        else:
            animate_collapse()

    btn_expand.config(command=toggle_expand)
    btn_collapse.config(command=toggle_expand)
    last_track_id = None
    # --- Precarga de imagen y update de UI ---
    def update_ui():
        nonlocal precached_album_img, last_track_id
        while True:
            try:
                current = controller.sp.current_playback()
                if current and current["item"]:
                    # Título y autores separados
                    raw_title = current["item"]["name"]
                    raw_artists = ", ".join([a["name"] for a in current["item"]["artists"]])
                    title = truncate_text(raw_title, 28)
                    artists = truncate_text(raw_artists, 32)
                else:
                    title = "Spotify inactivo"
                    artists = ""

                title_label_compact.config(text=title)
                artist_label_compact.config(text=artists)
                title_label_expanded.config(text=title)
                artist_label_expanded.config(text=artists)

                # Actualiza el ícono de play/pause según el estado real
                if current and current.get("is_playing"):
                    btn_play_pause.config(image=icon_pause)
                else:
                    btn_play_pause.config(image=icon_play)

                # Precarga la imagen del álbum
                if current and current["item"]["album"]["images"]:
                    img_url = current["item"]["album"]["images"][0]["url"]
                    img_data = requests.get(img_url).content
                    img = Image.open(io.BytesIO(img_data)).resize((ALBUM_IMG_SIZE, ALBUM_IMG_SIZE))
                    precached_album_img = ImageTk.PhotoImage(img)
                    album_img_label.config(image=precached_album_img)
                    album_img_label.image = precached_album_img

                    # Imagen compacta (más pequeña)
                    img_compact = Image.open(io.BytesIO(img_data)).resize((40, 40))
                    img_compact = rounded_image(img_compact, radius=10)  # Ajusta el radio a tu gusto
                    precached_album_img_compact = ImageTk.PhotoImage(img_compact)
                    album_img_label_compact.config(image=precached_album_img_compact)
                    album_img_label_compact.image = precached_album_img_compact

                # Actualiza barra de progreso tipo Spotify y tiempos
                if current and current["item"]:
                    total_sec = current["item"]["duration_ms"] // 1000
                    current_sec = current["progress_ms"] // 1000
                    draw_progress_bar(current_sec, total_sec)
                    # Formatea los tiempos mm:ss
                    def fmt(sec):
                        return f"{sec//60}:{sec%60:02d}"
                    label_time_current.config(text=fmt(current_sec))
                    label_time_total.config(text=fmt(total_sec))
                if current and current["item"]:
                    track_id = current["item"]["id"]
                if track_id != last_track_id:
                    # solo consultar si la canción cambió
                    is_fav = controller.safe_api_call(controller.sp.current_user_saved_tracks_contains, [track_id])[0]
                    update_heart_icon(is_fav)
                    last_track_id = track_id
            except Exception as e:
                title_label_compact.config(text="Error: reinicia el programa")
                title_label_expanded.config(text="Error: reinicia el programa")
                btn_play_pause.config(image=icon_play)
            time.sleep(0.1)  # Actualiza 100ms

    def toggle_play_pause():
        try:
            current = controller.sp.current_playback()
            if current and current["is_playing"]:
                controller.pause()
                btn_play_pause.config(image=icon_play)
            else:
                controller.play()
                btn_play_pause.config(image=icon_pause)
        except:
            pass

    btn_play_pause.config(command=toggle_play_pause)

    threading.Thread(target=update_ui, daemon=True).start()

    # --- Volumen popup ---
    def show_volume_popup(event=None):
        # Si ya existe, destrúyelo
        if hasattr(show_volume_popup, "popup") and show_volume_popup.popup.winfo_exists():
            show_volume_popup.popup.destroy()

        # Crear ventana popup sin bordes
        popup = tk.Toplevel(root)
        show_volume_popup.popup = popup
        popup.overrideredirect(True)
        popup.configure(bg="#222222")
        popup.attributes("-topmost", True)

        # Posicionar el popup justo encima del botón de volumen
        bx = btn_vol.winfo_rootx()
        by = btn_vol.winfo_rooty()
        bw = btn_vol.winfo_width()
        bh = btn_vol.winfo_height()
        popup.geometry(f"40x120+{bx + bw//2 - 20}+{by - 120}")

        # Obtener volumen actual
        try:
            current = controller.get_current_track()
            if current and "device" in current and current["device"]:
                current_vol = current["device"]["volume_percent"]
            else:
                current_vol = 50
        except:
            current_vol = 50

        # --- Canvas de volumen ---
        CANVAS_W = 24
        CANVAS_H = 100
        BAR_W = 8
        BAR_X = (CANVAS_W - BAR_W) // 2
        BAR_Y0 = 10
        BAR_Y1 = CANVAS_H - 10

        canvas = tk.Canvas(popup, width=CANVAS_W, height=CANVAS_H, bg="#222222", highlightthickness=0, bd=0)
        canvas.pack(padx=8, pady=10)

        def draw_volume(vol):
            canvas.delete("all")
            # Fondo barra
            canvas.create_rectangle(BAR_X, BAR_Y0, BAR_X+BAR_W, BAR_Y1, fill="#444444", outline="#444444", width=0)
            # Barra de volumen
            filled_y = BAR_Y1 - int((vol/100)*(BAR_Y1-BAR_Y0))
            canvas.create_rectangle(BAR_X, filled_y, BAR_X+BAR_W, BAR_Y1, fill="#1DB954", outline="#1DB954", width=0)
            # Thumb (rectángulo)
            thumb_height = 10  # Alto del thumb
            thumb_width = BAR_W + 4  # Ancho del thumb
            canvas.create_rectangle(
                BAR_X-2, filled_y-thumb_height//2, BAR_X+BAR_W+2, filled_y+thumb_height//2,
                fill="#1DB954", outline="#1DB954"
            )

        draw_volume(current_vol)

        def set_volume_from_click(event):
            # Calcula el volumen según la posición Y del click
            y = event.y
            y = min(max(y, BAR_Y0), BAR_Y1)
            vol = int(100 * (BAR_Y1 - y) / (BAR_Y1 - BAR_Y0))
            draw_volume(vol)
            try:
                controller.safe_api_call(controller.sp.volume, vol)
            except:
                pass

        canvas.bind("<Button-1>", set_volume_from_click)
        canvas.bind("<B1-Motion>", set_volume_from_click)

        # Cerrar popup al perder foco
        popup.bind("<FocusOut>", lambda e: popup.destroy())
        popup.focus_force()

    btn_vol.config(command=show_volume_popup)
    def update_heart_icon(is_fav):
        if is_fav:
            btn_heart.config(image=icon_heart_filled)
        else:
            btn_heart.config(image=icon_heart_empty)

    def toggle_favorite():
        try:
            current = controller.get_current_track()
            if current and current["item"]:
                track_id = current["item"]["id"]
                is_fav = controller.safe_api_call(controller.sp.current_user_saved_tracks_contains, [track_id])[0]
                if is_fav:
                    controller.safe_api_call(controller.sp.current_user_saved_tracks_delete, [track_id])
                    update_heart_icon(False)
                else:
                    controller.safe_api_call(controller.sp.current_user_saved_tracks_add, [track_id])
                    update_heart_icon(True)
        except Exception as e:
            print("Error al actualizar favoritos:", e)

    btn_heart.config(command=toggle_favorite)

    root.mainloop()

# === MAIN ===
def main():
    load_credentials()
    if not client_id or not client_secret:
        prompt_client_credentials()

    tokens = load_tokens()

    if not tokens:
        code_holder = {}
        start_auth_server(code_holder)

        auth_url = build_auth_url()
        print("Abriendo navegador para autenticación...")
        webbrowser.open(auth_url)

        print("Esperando autenticación...")
        while "code" not in code_holder:
            time.sleep(0.2)

        try:
            tokens = exchange_code_for_token(code_holder["code"])
            save_tokens(tokens)
        except requests.HTTPError as e:
            # Intenta extraer el error_description del JSON de respuesta
            try:
                error_json = e.response.json()
                error_msg = error_json.get("error_description", str(e))
            except Exception:
                error_msg = str(e)
            print("Mostrando modal de credenciales por error:", error_msg)
            prompt_client_credentials(force=True, error_msg=error_msg)
            # Reinicia el flujo
            main()
            return
    else:
        print("✅ Tokens cargados desde archivo.")

    try:
        controller = SpotifyController(tokens["access_token"], tokens.get("refresh_token"), tokens.get("state"))
        controller.refresh_if_needed()
        # Inicia el hilo de auto-refresh
        auto_refresh_loop(controller)
    except Exception as e:
        print("Error con los tokens, limpiando sesión y pidiendo login otra vez.")
        clear_session()
        sys.exit(1)

    create_spotify_widget(controller)

if __name__ == "__main__":
    main()