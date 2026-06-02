import tkinter as tk
from tkinter import ttk, scrolledtext
import subprocess
import threading
import sys
import os

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Uydu Çarpışma Önleme Simülasyonu - Arayüz")
        self.root.geometry("1100x850")
        
        # Modern bir stil uygulayalım
        style = ttk.Style()
        if 'clam' in style.theme_names():
            style.theme_use('clam')
            
        # Yazı tiplerini büyütelim
        style.configure("TRadiobutton", font=("Helvetica", 14))
        style.configure("TButton", font=("Helvetica", 14, "bold"), padding=8)
        style.configure("TLabelframe.Label", font=("Helvetica", 14, "bold"))
        
        # Ana Çerçeve
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Başlık
        title_label = ttk.Label(main_frame, text="Uydu Çarpışma Önleme (Collision Avoidance)", font=("Helvetica", 24, "bold"))
        title_label.pack(pady=(0, 5))
        
        subtitle_label = ttk.Label(main_frame, text="Simülasyon ve Modelleme Dersi", font=("Helvetica", 16))
        subtitle_label.pack(pady=(0, 20))
        
        # Kontrol Çerçevesi (Radyo Butonları)
        control_frame = ttk.LabelFrame(main_frame, text="Çalıştırma Seçenekleri", padding="15")
        control_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.run_option = tk.StringVar(value="all")
        
        options = [
            ("Senaryo 1: Düşük Risk (Near-Miss)", "1"),
            ("Senaryo 2: Yüksek Risk (Kaçınma Manevrası)", "2"),
            ("Senaryo 3: Delta-V Duyarlılık Analizi", "3"),
            ("Senaryo 4: Çoklu Enkaz (Multi-Debris)", "4"),
            ("Tüm Senaryoları Çalıştır", "all"),
            ("V&V: Doğrulama ve Geçerleme Testleri", "verify"),
            ("Monte Carlo Simülasyonu (N=200)", "monte_carlo")
        ]
        
        for text, val in options:
            rb = ttk.Radiobutton(control_frame, text=text, variable=self.run_option, value=val)
            rb.pack(anchor=tk.W, pady=6)
            
        # Çalıştır Butonu
        self.run_btn = ttk.Button(control_frame, text="Seçileni Çalıştır", command=self.start_simulation)
        self.run_btn.pack(pady=(15, 5))
        
        # Çıktı Çerçevesi (Loglar)
        output_frame = ttk.LabelFrame(main_frame, text="Konsol Çıktısı", padding="15")
        output_frame.pack(fill=tk.BOTH, expand=True)
        
        self.output_text = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, font=("Consolas", 14), bg="#1e1e1e", fg="#d4d4d4")
        self.output_text.pack(fill=tk.BOTH, expand=True)
        
        # Sağ Tık Menüsü (Kopyalamak için)
        self.context_menu = tk.Menu(self.output_text, tearoff=0)
        self.context_menu.add_command(label="Kopyala", command=self.copy_text)
        self.output_text.bind("<Button-3>", self.show_context_menu)

    def show_context_menu(self, event):
        self.context_menu.tk_popup(event.x_root, event.y_root)

    def copy_text(self):
        try:
            selected_text = self.output_text.selection_get()
            self.root.clipboard_clear()
            self.root.clipboard_append(selected_text)
        except tk.TclError:
            pass # Metin seçilmemişse hata verme
        
    def start_simulation(self):
        # Butonu devre dışı bırak (birden fazla basılmasını önle)
        self.run_btn.config(state=tk.DISABLED)
        self.output_text.delete(1.0, tk.END)
        self.output_text.insert(tk.END, "Simülasyon başlatılıyor...\n")
        self.output_text.insert(tk.END, "-" * 50 + "\n\n")
        
        option = self.run_option.get()
        
        # Komut satırı argümanlarını belirle (main.py'nin parametrelerine göre)
        cmd = [sys.executable, "main.py"]
        if option in ["1", "2", "3", "4", "all"]:
            cmd.extend(["--scenario", option])
        elif option == "verify":
            cmd.append("--verify")
        elif option == "monte_carlo":
            cmd.append("--monte-carlo")
            
        # UI donmaması için işlemi ayrı bir thread'de (iş parçacığında) çalıştır
        thread = threading.Thread(target=self.run_subprocess, args=(cmd,))
        thread.daemon = True # Ana pencere kapanırsa thread de kapansın
        thread.start()
        
    def run_subprocess(self, cmd):
        try:
            # subprocess.Popen ile komutu arka planda çalıştır
            # bufsize=1 ve text=True ile çıktıyı satır satır okuyabiliriz
            # encoding='utf-8' Türkçe karakterler için önemli
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8'
            )
            
            # Gelen çıktıları satır satır arayüze ekle
            for line in process.stdout:
                # Tkinter arayüzünü doğrudan başka thread'den güncellemek güvenli değildir.
                # after(0, ...) ile işlemi ana thread'e (UI thread) havale ediyoruz.
                self.root.after(0, self.append_output, line)
                
            process.wait()
            self.root.after(0, self.append_output, f"\n--- İşlem tamamlandı (Çıkış Kodu: {process.returncode}) ---\n")
            self.root.after(0, self.append_output, "Grafikler 'results' klasörüne kaydedildi.\n")
            
        except Exception as e:
            self.root.after(0, self.append_output, f"\nHATA: {str(e)}\n")
            
        finally:
            # İşlem bitince butonu tekrar aktif et
            self.root.after(0, self.enable_button)
            
    def append_output(self, text):
        self.output_text.insert(tk.END, text)
        self.output_text.see(tk.END) # Otomatik en alta kaydır
        
    def enable_button(self):
        self.run_btn.config(state=tk.NORMAL)

if __name__ == "__main__":
    # Eğer bu dizinde çalıştırılmadıysa, main.py'yi bulabilmek için dizini değiştir
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    root = tk.Tk()
    app = App(root)
    root.mainloop()
