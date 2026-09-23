# -*- coding: utf-8 -*-
"""
Luama — сшиватель файлов (Lua, luau, txt, json, cfg, ini...)
Соединяет несколько текстовых файлов в один с настраиваемым порядком,
разделителями, минификацией и предпросмотром результата.
"""

import os
import sys
import glob
import json
import shutil
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    from PIL import Image, ImageTk, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

DEFAULT_MASK = "*.lua;*.luau;*.txt;*.json;*.cfg;*.ini"

# ---------------- ПАЛИТРА ----------------
BG        = "#1e1f29"   # фон окна
BG_PANEL  = "#262838"   # панели
BG_INPUT  = "#171822"   # поля ввода
BG_HOVER  = "#33364d"
FG        = "#e8e9f3"   # основной текст
FG_DIM    = "#8b8fa8"   # приглушённый текст
ACCENT    = "#7c6cff"   # фиолетовый акцент
ACCENT2   = "#39d0a4"   # зелёный акцент
DANGER    = "#ff5c7a"
BORDER    = "#3a3d55"

FONT      = ("Segoe UI", 10)
FONT_B    = ("Segoe UI", 10, "bold")
FONT_T    = ("Segoe UI", 16, "bold")
FONT_MONO = ("Consolas", 10)


class LuaCompilerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Luama — сшиватель файлов")
        self.geometry("980x640")
        self.minsize(840, 560)
        self.configure(bg=BG)
        self.files = []  # список путей к файлам

        self._set_icon()
        self._build_header()
        self._build_body()
        self._build_statusbar()
        self.bind("<Control-o>", lambda e: self.add_files())
        self.bind("<Control-s>", lambda e: self.compile())
        self.bind("<Control-p>", lambda e: self.preview())
        self.bind("<Control-b>", lambda e: self.copy_result())
        self.bind("<Delete>", lambda e: self.remove_selected())

    def _set_icon(self):
        """Иконка окна: для .py берём icon.ico рядом со скриптом; у exe иконка уже в ресурсах."""
        try:
            if not getattr(sys, "frozen", False):
                icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
                if os.path.exists(icon_path):
                    self.iconbitmap(icon_path)
        except Exception:
            pass

    # ---------------- помощники ----------------
    @staticmethod
    def _shift(hexcolor):
        r, g, b = int(hexcolor[1:3], 16), int(hexcolor[3:5], 16), int(hexcolor[5:7], 16)
        return "#%02x%02x%02x" % (min(255, r + 25), min(255, g + 25), min(255, b + 25))

    def make_button(self, parent, text, command, bg=ACCENT, fg="#ffffff"):
        btn = tk.Label(parent, text=text, bg=bg, fg=fg, font=FONT_B,
                       padx=14, pady=7, cursor="hand2")
        btn.bind("<Button-1>", lambda e: command())
        base = bg
        hover = self._shift(bg)
        btn.bind("<Enter>", lambda e: btn.configure(bg=hover))
        btn.bind("<Leave>", lambda e: btn.configure(bg=base))
        return btn

    # ---------------- шапка ----------------
    def _make_lattice(self, w, h, color="#30324a", bgc=BG_PANEL, step=26):
        """Рисует ромбовый узор (diamond lattice) и возвращает PhotoImage."""
        img = Image.new("RGB", (w, h), bgc)
        d = ImageDraw.Draw(img)
        for k in range(-h, w + h, step):
            d.line([(k, 0), (k + h, h)], fill=color, width=2)
            d.line([(k, 0), (k - h, h)], fill=color, width=2)
        return ImageTk.PhotoImage(img)

    def _build_header(self):
        header = tk.Frame(self, bg=BG_PANEL, pady=14, padx=20)
        header.pack(fill="x")
        if HAS_PIL:
            # фоновый ромбовый узор на всей шапке
            self._header_pattern = self._make_lattice(1400, 90)
            pattern_lbl = tk.Label(header, image=self._header_pattern, bg=BG_PANEL)
            pattern_lbl.place(x=0, y=0, relwidth=1, relheight=1)
            header.lift()
            # логотип-лама перед названием
            base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
            llama_path = os.path.join(base_dir, "llama_gui.png")
            if os.path.exists(llama_path):
                self._llama_img = tk.PhotoImage(file=llama_path)
                tk.Label(header, image=self._llama_img, bg=BG_PANEL).pack(side="left", padx=(0, 8))
        tk.Label(header, text="◆ Luama", bg=BG_PANEL, fg=ACCENT,
                 font=FONT_T).pack(side="left")
        tk.Label(header, text="сшивка файлов в один", bg=BG_PANEL, fg=FG_DIM,
                 font=FONT).pack(side="left", padx=12, pady=(6, 0))

    # ---------------- тело ----------------
    def _build_body(self):
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=20, pady=14)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # --- левая панель: список файлов ---
        left = tk.Frame(body, bg=BG_PANEL, padx=14, pady=14)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        tk.Label(left, text="Файлы (порядок сшивки сверху вниз, 2×клик = просмотр)",
                 bg=BG_PANEL, fg=FG, font=FONT_B).pack(anchor="w")

        btns = tk.Frame(left, bg=BG_PANEL)
        btns.pack(fill="x", pady=(10, 8))
        self.make_button(btns, "+ Файл", self.add_files).pack(side="left")
        self.make_button(btns, "+ Папка", self.add_folder, bg=BG_HOVER).pack(side="left", padx=6)
        self.make_button(btns, "✕ Очистить", self.clear_files, bg=BG_HOVER).pack(side="right")

        # маска расширений + проекты
        row_mask = tk.Frame(left, bg=BG_PANEL)
        row_mask.pack(fill="x", pady=(0, 6))
        tk.Label(row_mask, text="Маска:", bg=BG_PANEL, fg=FG_DIM, font=FONT).pack(side="left")
        self.mask_entry = tk.Entry(row_mask, bg=BG_INPUT, fg=FG, font=FONT,
                                   insertbackground=ACCENT, relief="flat",
                                   highlightthickness=1, highlightbackground=BORDER,
                                   highlightcolor=ACCENT)
        self.mask_entry.insert(0, DEFAULT_MASK)
        self.mask_entry.pack(side="left", fill="x", expand=True, padx=6, ipady=3)

        row_proj = tk.Frame(left, bg=BG_PANEL)
        row_proj.pack(fill="x", pady=(0, 8))
        self.make_button(row_proj, "💾 Проект", self.save_project, bg=BG_HOVER).pack(side="left")
        self.make_button(row_proj, "📂 Открыть", self.load_project, bg=BG_HOVER).pack(side="left", padx=6)
        self.make_button(row_proj, "🔧 Сортировать", self.sort_files, bg=BG_HOVER).pack(side="right")

        listbox_frame = tk.Frame(left, bg=BORDER)
        listbox_frame.pack(fill="both", expand=True)
        self.listbox = tk.Listbox(
            listbox_frame, bg=BG_INPUT, fg=FG, font=FONT_MONO,
            selectbackground=ACCENT, selectforeground="#fff",
            activestyle="none", bd=0, highlightthickness=0,
        )
        sb = tk.Scrollbar(listbox_frame, command=self.listbox.yview, bg=BG_PANEL,
                          troughcolor=BG_INPUT, width=10, bd=0, activebackground=ACCENT)
        self.listbox.configure(yscrollcommand=sb.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.listbox.bind("<Double-Button-1>", self.show_selected_file)
        self.listbox.bind("<<ListboxSelect>>", self.show_selected_file)

        ops = tk.Frame(left, bg=BG_PANEL)
        ops.pack(fill="x", pady=(8, 0))
        self.make_button(ops, "▲ Вверх", lambda: self.move(-1), bg=BG_HOVER).pack(side="left")
        self.make_button(ops, "▼ Вниз", lambda: self.move(1), bg=BG_HOVER).pack(side="left", padx=6)
        self.make_button(ops, "🔄 Инверт.", self.invert_files, bg=BG_HOVER).pack(side="left")
        self.make_button(ops, "🧹 Дубликаты", self.dedupe_files, bg=BG_HOVER).pack(side="left", padx=6)

        # --- опции ---
        options = tk.Frame(left, bg=BG_PANEL)
        options.pack(fill="x", pady=(12, 0))
        tk.Label(options, text="Опции", bg=BG_PANEL, fg=FG, font=FONT_B).pack(anchor="w")

        self.var_headers = tk.BooleanVar(value=True)
        self.var_strip = tk.BooleanVar(value=False)
        self.var_wrap = tk.BooleanVar(value=False)
        self.var_minify = tk.BooleanVar(value=False)

        for text, var in [
            ("Вставлять заголовок-комментарий перед каждым файлом", self.var_headers),
            ("Склейка модулей: убирать 'module(...)' и 'return M'", self.var_strip),
            ("Оборачивать каждый файл в do ... end (изоляция локальных)", self.var_wrap),
            ("Минификация: убрать комментарии и пустые строки", self.var_minify),
        ]:
            cb = tk.Checkbutton(
                options, text=text, variable=var, bg=BG_PANEL, fg=FG_DIM,
                activebackground=BG_PANEL, activeforeground=FG, selectcolor=BG_INPUT,
                font=FONT, bd=0, highlightthickness=0, anchor="w",
                command=self.preview,
            )
            cb.pack(anchor="w", pady=2)

        # --- правая панель: предпросмотр + вывод ---
        right = tk.Frame(body, bg=BG_PANEL, padx=14, pady=14)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        head = tk.Frame(right, bg=BG_PANEL)
        head.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        tk.Label(head, text="Предпросмотр результата", bg=BG_PANEL, fg=FG, font=FONT_B).pack(side="left")
        self.make_button(head, "⟳ Обновить", self.preview, bg=BG_HOVER).pack(side="right")
        self.make_button(head, "⧉ Копировать", self.copy_result, bg=BG_HOVER).pack(side="right", padx=6)
        self.make_button(head, "📄 Открыть", self.open_selected, bg=BG_HOVER).pack(side="right")
        self.make_button(head, "📁 В папке", self.reveal_selected, bg=BG_HOVER).pack(side="right", padx=6)

        out_frame = tk.Frame(right, bg=BORDER)
        out_frame.grid(row=1, column=0, sticky="nsew")
        self.output = tk.Text(
            out_frame, bg=BG_INPUT, fg=FG, font=FONT_MONO, bd=0,
            insertbackground=ACCENT, highlightthickness=0, wrap="none",
            state="disabled",
        )
        osb = tk.Scrollbar(out_frame, command=self.output.yview, bg=BG_PANEL,
                           troughcolor=BG_INPUT, width=10, bd=0, activebackground=ACCENT)
        self.output.configure(yscrollcommand=osb.set)
        self.output.pack(side="left", fill="both", expand=True)
        osb.pack(side="right", fill="y")

        # --- низ правой панели: имя вывода и сборка ---
        bottom = tk.Frame(right, bg=BG_PANEL)
        bottom.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        tk.Label(bottom, text="Имя выходного файла:", bg=BG_PANEL, fg=FG_DIM,
                 font=FONT).pack(side="left")
        self.out_entry = tk.Entry(bottom, bg=BG_INPUT, fg=FG, font=FONT,
                                  insertbackground=ACCENT, relief="flat",
                                  highlightthickness=1, highlightbackground=BORDER,
                                  highlightcolor=ACCENT)
        self.out_entry.insert(0, "compiled.lua")
        self.out_entry.pack(side="left", fill="x", expand=True, padx=8, ipady=5)
        self.make_button(bottom, "⚙ СШИТЬ И СОХРАНИТЬ", self.compile,
                         bg=ACCENT2, fg="#0b2b21").pack(side="right")

        self.make_button(ops, "✕ Удалить", self.remove_selected, bg=DANGER).pack(side="right")


    # ---------------- статусбар ----------------
    def _build_statusbar(self):
        self.status = tk.Label(self, text="Готово. Добавьте файлы (Ctrl+O).",
                               bg=BG_PANEL, fg=FG_DIM, font=FONT, anchor="w",
                               padx=14, pady=6)
        self.status.pack(fill="x", side="bottom")

    def set_status(self, text, color=FG_DIM):
        self.status.configure(text=text, fg=color)

    # ---------------- действия ----------------
    def get_masks(self):
        raw = self.mask_entry.get().strip() or DEFAULT_MASK
        return [m.strip().lower() for m in raw.split(";") if m.strip()]

    def add_files(self):
        exts = " ".join(m for m in self.get_masks() if m.startswith("*."))
        paths = filedialog.askopenfilenames(
            filetypes=[("Выбранные типы", exts or "*.*"), ("Все файлы", "*.*")])
        self._add(paths)

    def add_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        masks = self.get_masks()
        paths = []
        for m in masks:
            paths.extend(glob.glob(os.path.join(folder, "**", m), recursive=True))
        self._add(sorted(set(paths)))

    def _add(self, paths):
        added = 0
        for p in paths:
            if p not in self.files:
                self.files.append(p)
                added += 1
        self.refresh_list()
        self.set_status(f"Добавлено: {added}. Всего файлов: {len(self.files)}.", ACCENT2)

    def clear_files(self):
        self.files.clear()
        self.refresh_list()
        self.preview()
        self.set_status("Список очищен.")

    def refresh_list(self):
        self.listbox.delete(0, "end")
        for i, p in enumerate(self.files, 1):
            exists = os.path.exists(p)
            mark = "" if exists else "  ✖ (нет)"
            size = ""
            if exists:
                try:
                    kb = os.path.getsize(p) / 1024
                    size = f"  [{kb:.1f} КБ]"
                except OSError:
                    pass
            self.listbox.insert("end", f"{i:>2}.  {os.path.basename(p)}{size}{mark}")

    def show_selected_file(self, event=None):
        sel = self.listbox.curselection()
        if not sel:
            return
        path = self.files[sel[0]]
        if not os.path.exists(path):
            self.set_status(f"Файл отсутствует на диске: {path}", DANGER)
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                with open(path, "r", encoding="cp1251", errors="replace") as f:
                    content = f.read()
            except OSError as e:
                self.set_status(f"Ошибка чтения: {e}", DANGER)
                return
        except OSError as e:
            self.set_status(f"Ошибка чтения: {e}", DANGER)
            return
        lines = content.splitlines()
        snippet = "\n".join(lines[:500])
        if len(lines) > 500:
            snippet += f"\n\n... ({len(lines) - 500} строк ниже, см. полный файл кнопкой «Открыть»)"
        header = f"-- Просмотр: {path} | строк: {len(lines)}\n\n"
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", header + snippet)
        self.output.configure(state="disabled")
        self.set_status(f"Показан файл: {os.path.basename(path)} (двойной клик = просмотр)", ACCENT2)

    def move(self, direction):
        sel = self.listbox.curselection()
        if not sel:
            return
        i = sel[0]
        j = i + direction
        if 0 <= j < len(self.files):
            self.files[i], self.files[j] = self.files[j], self.files[i]
            self.refresh_list()
            self.listbox.selection_set(j)
            self.listbox.activate(j)

    def remove_selected(self):
        sel = self.listbox.curselection()
        if sel:
            del self.files[sel[0]]
            self.refresh_list()
            self.preview()

    def sort_files(self):
        self.files.sort(key=lambda p: os.path.basename(p).lower())
        self.refresh_list()
        self.preview()
        self.set_status("Список отсортирован по имени.", ACCENT)

    def invert_files(self):
        self.files.reverse()
        self.refresh_list()
        self.preview()
        self.set_status("Порядок файлов инвертирован.", ACCENT)

    def dedupe_files(self):
        seen, out = set(), []
        for p in self.files:
            k = os.path.normcase(os.path.abspath(p))
            if k not in seen:
                seen.add(k)
                out.append(p)
        removed = len(self.files) - len(out)
        self.files = out
        self.refresh_list()
        self.preview()
        self.set_status(f"Удалено дубликатов: {removed}.", ACCENT2)

    def open_selected(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        path = self.files[sel[0]]
        if not os.path.exists(path):
            messagebox.showerror("Файл не найден", f"Файл не существует:\n{path}")
            return
        try:
            if sys.platform == "win32":
                os.startfile(path)
            else:
                subprocess.Popen(["xdg-open", path])
        except OSError as e:
            messagebox.showerror("Ошибка", f"Не удалось открыть файл: {e}")

    def reveal_selected(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        path = os.path.abspath(self.files[sel[0]])
        folder = os.path.dirname(path)
        if not os.path.isdir(folder):
            messagebox.showerror("Папка не найдена", f"Папка не существует:\n{folder}")
            return
        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", "/select,", path])
            else:
                subprocess.Popen(["xdg-open", folder])
        except OSError as e:
            messagebox.showerror("Ошибка", f"Не удалось открыть папку: {e}")

    # ---------------- проекты ----------------
    def save_project(self):
        if not self.files:
            messagebox.showwarning("Пусто", "Сначала добавьте файлы в список.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".luama",
            initialfile="project.luama",
            filetypes=[("Проект Luama", "*.luama"), ("Все файлы", "*.*")],
            title="Сохранить проект",
        )
        if not path:
            return
        data = {"version": 1, "files": self.files,
                "options": {
                    "headers": self.var_headers.get(),
                    "strip": self.var_strip.get(),
                    "wrap": self.var_wrap.get(),
                    "minify": self.var_minify.get(),
                },
                "mask": self.mask_entry.get().strip() or DEFAULT_MASK,
                "out_name": self.out_entry.get().strip() or "compiled.lua"}
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.set_status("Проект сохранён: " + path, ACCENT2)
        except OSError as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить проект: {e}")

    def load_project(self):
        path = filedialog.askopenfilename(
            filetypes=[("Проект Luama", "*.luama"), ("Все файлы", "*.*")],
            title="Открыть проект")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            messagebox.showerror("Ошибка", f"Не удалось открыть проект: {e}")
            return
        self.files = list(data.get("files", []))
        opts = data.get("options", {})
        self.var_headers.set(opts.get("headers", True))
        self.var_strip.set(opts.get("strip", False))
        self.var_wrap.set(opts.get("wrap", False))
        self.var_minify.set(opts.get("minify", False))
        if data.get("mask"):
            self.mask_entry.delete(0, "end")
            self.mask_entry.insert(0, data["mask"])
        if data.get("out_name"):
            self.out_entry.delete(0, "end")
            self.out_entry.insert(0, data["out_name"])
        self.refresh_list()
        self.preview()
        missing = [p for p in self.files if not os.path.exists(p)]
        if missing:
            self.set_status(f"Проект загружен. Отсутствующих файлов: {len(missing)} (помечены ✖).", DANGER)
        else:
            self.set_status("Проект загружен.", ACCENT2)

    # ---------------- сборка ----------------
    @staticmethod
    def _strip_module_lines(text):
        lines = []
        for line in text.splitlines():
            s = line.strip()
            if s in ("module(...)", "return M", "return m") or s.startswith("module("):
                continue
            lines.append(line)
        return "\n".join(lines)

    @staticmethod
    def _minify(text):
        lines = []
        for line in text.splitlines():
            s = line.strip()
            if not s or s.startswith("--"):
                continue
            lines.append(line)
        return "\n".join(lines)

    def build_merged(self):
        parts = []
        errors = []
        for i, path in enumerate(self.files, 1):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                try:
                    with open(path, "r", encoding="cp1251", errors="replace") as f:
                        content = f.read()
                except OSError as e:
                    errors.append(f"Не удалось прочитать: {path} ({e})")
                    continue
            except OSError as e:
                errors.append(f"Не удалось прочитать: {path} ({e})")
                continue

            name = os.path.basename(path)
            if self.var_headers.get():
                parts.append(f"-- {'=' * 60}\n-- [{i}/{len(self.files)}] {name}\n-- {'=' * 60}")
            if self.var_strip.get():
                content = self._strip_module_lines(content)
            if self.var_minify.get():
                content = self._minify(content)
            if self.var_wrap.get():
                parts.append("do\n" + content.rstrip("\n") + "\nend")
            else:
                parts.append(content.rstrip("\n"))

        header = "-- Сгенерировано Luama | файлов: %d\n" % len(self.files)
        return header + "\n\n".join(parts) + "\n", errors

    def preview(self):
        merged, errors = self.build_merged()
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", merged)
        self.output.configure(state="disabled")
        if errors:
            self.set_status(" | ".join(errors), DANGER)
        else:
            total_lines = merged.count("\n") + 1
            size_kb = len(merged.encode("utf-8")) / 1024
            self.set_status(
                f"Предпросмотр: файлов {len(self.files)} | строк {total_lines} | "
                f"{size_kb:.1f} КБ", ACCENT2)

    def copy_result(self):
        merged, errors = self.build_merged()
        self.clipboard_clear()
        self.clipboard_append(merged)
        self.preview()
        self.set_status("Результат скопирован в буфер обмена.", ACCENT2)

    def compile(self):
        if not self.files:
            messagebox.showwarning("Нет файлов", "Сначала добавьте хотя бы один файл.")
            return
        out_name = self.out_entry.get().strip() or "compiled.lua"
        out_path = filedialog.asksaveasfilename(
            defaultextension=".lua", initialfile=out_name,
            filetypes=[("Lua файлы", "*.lua"), ("Все файлы", "*.*")],
            title="Куда сохранить скомпилированный файл",
        )
        if not out_path:
            return
        merged, errors = self.build_merged()
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(merged)
        if errors:
            messagebox.showwarning("Готово с ошибками",
                                   "Файл сохранён, но были проблемы:\n\n" + "\n".join(errors))
            self.set_status("Сохранено с ошибками: " + out_path, DANGER)
        else:
            messagebox.showinfo("Готово",
                                f"Файлы успешно сшиты:\n{out_path}\n\nРазмер: {len(merged)} символов.")
            self.set_status("Сохранено: " + out_path, ACCENT2)


if __name__ == "__main__":
    app = LuaCompilerApp()
    app.mainloop()

