import logging
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
from pathlib import Path
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
import tempfile
import time
import os
import requests
from bs4 import BeautifulSoup
import markitdown
import pytube
from markdownify import markdownify

# Funciones de utilidad
def get_supported_extensions():
    return [
        '.pdf', '.docx', '.pptx', '.html', '.txt',
        '.csv', '.xlsx', '.ppt', '.doc', '.xml'
    ]

def ensure_directory_exists(directory):
    Path(directory).mkdir(parents=True, exist_ok=True)

class WebToMarkdownConverter:
    def __init__(self):
        self.cancel_requested = False
        self.executor = ThreadPoolExecutor(max_workers=1)
    
    def convert_url(self, url, output_path=None, progress_callback=None):
        """
        Convierte una página web a formato Markdown.
        
        Args:
            url: URL de la página web a convertir
            output_path: Ruta donde guardar el archivo convertido
            progress_callback: Función para reportar el progreso (0-100)
            
        Returns:
            True si la conversión fue exitosa, False en caso contrario
        """
        try:
            if progress_callback:
                progress_callback(10)
                
            # Determinar si es una URL de YouTube
            is_youtube = "youtube.com" in url or "youtu.be" in url
            
            if is_youtube:
                return self.convert_youtube(url, output_path, progress_callback)
            
            # Preparar la ruta de salida
            if output_path is None:
                # Extraer un nombre de archivo de la URL
                from urllib.parse import urlparse
                parsed_url = urlparse(url)
                domain = parsed_url.netloc.replace("www.", "")
                path = parsed_url.path.strip("/").replace("/", "_")
                if not path:
                    path = "index"
                output_filename = f"{domain}_{path}.md"
                output_path = str(Path("output_files") / output_filename)
            
            ensure_directory_exists(Path(output_path).parent)
            
            if progress_callback:
                progress_callback(20)
            
            # Descargar la página web
            logging.info(f"Descargando: {url}")
            response = requests.get(url)
            response.raise_for_status()
            
            if progress_callback:
                progress_callback(50)
            
            # Convertir HTML a Markdown usando markdownify
            logging.info("Convirtiendo HTML a Markdown")
            markdown_content = markdownify(response.text)
            
            if progress_callback:
                progress_callback(80)
            
            # Guardar el resultado
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            if progress_callback:
                progress_callback(100)
                
            logging.info(f"Conversión completada: {output_path}")
            return True
            
        except Exception as e:
            logging.error(f"Error al convertir URL: {e}")
            return False
    
    def convert_youtube(self, url, output_path=None, progress_callback=None):
        """
        Convierte un video de YouTube a formato Markdown.
        
        Args:
            url: URL del video de YouTube
            output_path: Ruta donde guardar el archivo convertido
            progress_callback: Función para reportar el progreso (0-100)
            
        Returns:
            True si la conversión fue exitosa, False en caso contrario
        """
        try:
            if progress_callback:
                progress_callback(10)
            
            # Preparar la ruta de salida
            if output_path is None:
                # Extraer un nombre de archivo de la URL
                from urllib.parse import urlparse
                parsed_url = urlparse(url)
                video_id = parsed_url.query.split('v=')[-1].split('&')[0] if 'v=' in parsed_url.query else parsed_url.path.split('/')[-1]
                output_filename = f"youtube_{video_id}.md"
                output_path = str(Path("output_files") / output_filename)
            
            ensure_directory_exists(Path(output_path).parent)
            
            if progress_callback:
                progress_callback(30)
            
            # Usar pytube para obtener información del video
            logging.info(f"Procesando video de YouTube: {url}")
            from pytube import YouTube
            yt = YouTube(url)
            
            if progress_callback:
                progress_callback(50)
            
            # Crear contenido Markdown con la información del video
            title = yt.title
            author = yt.author
            description = yt.description
            thumbnail_url = yt.thumbnail_url
            
            markdown_content = f"# {title}\n\n"
            markdown_content += f"**Autor:** {author}\n\n"
            markdown_content += f"**URL:** {url}\n\n"
            markdown_content += f"![Thumbnail]({thumbnail_url})\n\n"
            markdown_content += "## Descripción\n\n"
            markdown_content += description.replace('\n', '\n\n')
            
            if progress_callback:
                progress_callback(80)
            
            # Guardar el resultado
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            if progress_callback:
                progress_callback(100)
                
            logging.info(f"Conversión completada: {output_path}")
            return True
            
        except Exception as e:
            logging.error(f"Error al convertir video de YouTube: {e}")
            return False
    
    def convert_url_async(self, url, output_path=None, progress_callback=None, completion_callback=None):
        """
        Convierte una URL a Markdown de forma asíncrona.
        
        Args:
            url: URL a convertir
            output_path: Ruta donde guardar el archivo convertido
            progress_callback: Función para reportar el progreso
            completion_callback: Función a llamar cuando se complete la conversión
        """
        def task():
            result = self.convert_url(url, output_path, progress_callback)
            if completion_callback:
                completion_callback(result, output_path)
        
        return self.executor.submit(task)
    
    def cancel_conversion(self):
        """Cancela la conversión en curso."""
        self.cancel_requested = True


class DoclingToMarkdownConverter:
    def __init__(self):
        self.process = None
        self.cancel_requested = False
        self.executor = ThreadPoolExecutor(max_workers=1)
    
    def convert_file(self, input_path, output_path=None, progress_callback=None):
        """
        Convierte un archivo a formato Markdown usando docling.
        
        Args:
            input_path: Ruta del archivo a convertir
            output_path: Ruta donde guardar el archivo convertido
            progress_callback: Función para reportar el progreso (0-100)
            
        Returns:
            True si la conversión fue exitosa, False en caso contrario
        """
        try:
            if not Path(input_path).exists():
                logging.error(f"El archivo no existe: {input_path}")
                return False
            
            if Path(input_path).suffix.lower() not in get_supported_extensions():
                logging.error(f"Formato no soportado: {input_path}")
                return False
            
            if output_path is None:
                input_path_obj = Path(input_path)
                output_filename = input_path_obj.stem + '.md'
                output_path = str(Path("output_files") / output_filename)
            ensure_directory_exists(Path(output_path).parent)
            
            # Reiniciar el estado de cancelación
            self.cancel_requested = False
            
            logging.info(f"Convirtiendo: {input_path}")
            
            # Reportar inicio de progreso
            if progress_callback:
                progress_callback(10)
            
            # Ejecutar docling con opciones optimizadas
            cmd = ["docling", input_path, "--output", output_path]
            
            # Para archivos grandes, añadir opciones de optimización si están disponibles
            file_size = Path(input_path).stat().st_size
            if file_size > 5 * 1024 * 1024:  # 5MB
                # Añadir opciones para optimizar el procesamiento de archivos grandes
                # (estas opciones dependen de las capacidades de docling)
                cmd.extend(["--optimize-large-files"])
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            # Monitorear el progreso
            stdout_lines = []
            stderr_lines = []
            
            while self.process.poll() is None:
                if self.cancel_requested:
                    self.process.terminate()
                    logging.info("Conversión cancelada por el usuario")
                    return False
                
                # Leer salida sin bloquear
                stdout_line = self.process.stdout.readline()
                if stdout_line:
                    stdout_lines.append(stdout_line)
                
                stderr_line = self.process.stderr.readline()
                if stderr_line:
                    stderr_lines.append(stderr_line)
                
                # Actualizar progreso (estimado)
                if progress_callback:
                    # Incrementar progreso gradualmente hasta 90%
                    # El 100% se reportará al finalizar
                    progress_callback(min(90, 10 + len(stdout_lines) * 2))
                
                time.sleep(0.1)
            
            # Leer cualquier salida restante
            stdout, stderr = self.process.communicate()
            if stdout:
                stdout_lines.append(stdout)
            if stderr:
                stderr_lines.append(stderr)
            
            if self.process.returncode == 0:
                logging.info(f"Archivo convertido exitosamente: {input_path} -> {output_path}")
                if progress_callback:
                    progress_callback(100)
                return True
            else:
                error_msg = ''.join(stderr_lines)
                logging.error(f"Error al convertir {input_path}: {error_msg}")
                return False
            
        except Exception as e:
            logging.error(f"Error al convertir {input_path}: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def convert_file_async(self, input_path, output_path=None, progress_callback=None, completion_callback=None):
        """
        Convierte un archivo de forma asíncrona.
        
        Args:
            input_path: Ruta del archivo a convertir
            output_path: Ruta donde guardar el archivo convertido
            progress_callback: Función para reportar el progreso (0-100)
            completion_callback: Función a llamar cuando se complete la conversión
        """
        def _convert_and_notify():
            result = self.convert_file(input_path, output_path, progress_callback)
            if completion_callback:
                completion_callback(result, output_path)
        
        self.executor.submit(_convert_and_notify)
    
    def cancel_conversion(self):
        """Cancela la conversión en curso"""
        self.cancel_requested = True
    
    def convert_directory(self, input_dir, output_dir, progress_callback=None, completion_callback=None):
        """
        Convierte todos los archivos soportados en un directorio.
        
        Args:
            input_dir: Directorio de entrada
            output_dir: Directorio de salida
            progress_callback: Función para reportar el progreso (0-100)
            completion_callback: Función a llamar cuando se complete la conversión
        """
        ensure_directory_exists(output_dir)
        
        input_path = Path(input_dir)
        stats = {
            'total_files': 0,
            'converted': 0,
            'failed': 0,
            'skipped': 0,
            'in_progress': 0
        }
        
        # Contar archivos primero para calcular el progreso
        supported_extensions = get_supported_extensions()
        files_to_convert = []
        
        for file_path in input_path.iterdir():
            if file_path.is_file():
                stats['total_files'] += 1
                
                if file_path.suffix.lower() in supported_extensions:
                    files_to_convert.append(file_path)
                else:
                    stats['skipped'] += 1
                    logging.info(f"Archivo omitido (formato no soportado): {file_path.name}")
        
        if not files_to_convert:
            if completion_callback:
                completion_callback(stats)
            return stats
        
        # Función para actualizar el progreso
        def update_progress():
            if progress_callback:
                progress = (stats['converted'] + stats['failed']) / len(files_to_convert) * 100
                progress_callback(progress)
        
        # Callback para cada archivo convertido
        def file_converted(success, output_path, file_path):
            if success:
                stats['converted'] += 1
            else:
                stats['failed'] += 1
            
            stats['in_progress'] -= 1
            update_progress()
            
            # Verificar si hemos terminado
            if stats['converted'] + stats['failed'] == len(files_to_convert):
                if completion_callback:
                    completion_callback(stats)
        
        # Iniciar conversión de cada archivo
        for file_path in files_to_convert:
            output_filename = file_path.stem + '.md'
            output_path = str(Path(output_dir) / output_filename)
            
            # Usar una función lambda para capturar el file_path actual
            callback = lambda success, out_path, fp=file_path: file_converted(success, out_path, fp)
            
            stats['in_progress'] += 1
            self.convert_file_async(str(file_path), output_path, None, callback)
        
        return stats
    
    def convert_directory_async(self, input_dir, output_dir, progress_callback=None, completion_callback=None):
        """
        Convierte un directorio de forma asíncrona.
        
        Args:
            input_dir: Directorio de entrada
            output_dir: Directorio de salida
            progress_callback: Función para reportar el progreso (0-100)
            completion_callback: Función a llamar cuando se complete la conversión
        """
        def _convert_and_notify():
            stats = self.convert_directory(input_dir, output_dir, progress_callback)
            if completion_callback:
                completion_callback(stats)
        
        self.executor.submit(_convert_and_notify)

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

class DoclingConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Docling a Markdown Converter")
        self.root.geometry("700x500")
        self.root.resizable(True, True)
        
        self.converter = DoclingToMarkdownConverter()
        self.web_converter = WebToMarkdownConverter()
        self.setup_ui()
        self.temp_dir = Path("temp_output")
        ensure_directory_exists(self.temp_dir)
        self.input_file = None
        self.output_file = None
        self.conversion_in_progress = False
        self.output_file_path = None
        self.current_mode = None
        
    def setup_ui(self):
        # Crear frame principal
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Notebook para pestañas
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Pestaña de conversión de archivos
        file_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(file_tab, text="Convertir Archivo")
        
        # Pestaña de conversión de páginas web
        web_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(web_tab, text="Convertir Página Web")
        
        # Pestaña de conversión de videos de YouTube
        youtube_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(youtube_tab, text="Convertir Video de YouTube")
        
        # Configurar pestaña de archivos
        self.setup_file_tab(file_tab)
        
        # Configurar pestaña de páginas web
        self.setup_web_tab(web_tab)
        
        # Configurar pestaña de YouTube
        self.setup_youtube_tab(youtube_tab)
    
    def setup_file_tab(self, parent):
        # Título
        title_label = ttk.Label(parent, text="Convertidor de Documentos a Markdown", font=("Helvetica", 14))
        title_label.pack(pady=5)
        
        # Descripción
        desc_label = ttk.Label(parent, text="Seleccione un archivo para convertirlo a formato Markdown")
        desc_label.pack(pady=5)
        
        # Frame para selección de archivo
        file_frame = ttk.Frame(parent)
        file_frame.pack(fill=tk.X, pady=5)
        
        self.file_path_var = tk.StringVar()
        file_entry = ttk.Entry(file_frame, textvariable=self.file_path_var, width=50)
        file_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        browse_button = ttk.Button(file_frame, text="Examinar", command=self.browse_file)
        browse_button.pack(side=tk.RIGHT, padx=5)
        
        # Formatos soportados
        formats_text = "Formatos soportados: " + ", ".join(get_supported_extensions())
        formats_label = ttk.Label(parent, text=formats_text)
        formats_label.pack(pady=5)
        
        # Barra de progreso
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(parent, variable=self.progress_var, maximum=100)
        self.progress.pack(fill=tk.X, pady=10)
        
        # Área de estado
        self.status_var = tk.StringVar(value="Listo para convertir")
        status_label = ttk.Label(parent, textvariable=self.status_var)
        status_label.pack(pady=5)
        
        # Frame para botones de acción
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=5)
        
        # Botón de conversión
        self.convert_button = ttk.Button(button_frame, text="Convertir a Markdown", 
                                        command=lambda: self.start_conversion("file"))
        self.convert_button.pack(side=tk.LEFT, padx=5)
        
        # Botón de cancelación (inicialmente deshabilitado)
        self.cancel_button = ttk.Button(button_frame, text="Cancelar", 
                                       command=lambda: self.cancel_conversion("file"), state=tk.DISABLED)
        self.cancel_button.pack(side=tk.LEFT, padx=5)
        
        # Botón de descarga (inicialmente deshabilitado)
        self.download_button = ttk.Button(button_frame, text="Descargar Markdown", 
                                         command=lambda: self.download_file("file"), state=tk.DISABLED)
        self.download_button.pack(side=tk.RIGHT, padx=5)
        
        # Información de tiempo estimado
        self.time_label = ttk.Label(parent, text="")
        self.time_label.pack(pady=5)
    
    def setup_web_tab(self, parent):
        # Título
        title_label = ttk.Label(parent, text="Convertidor de Páginas Web a Markdown", font=("Helvetica", 14))
        title_label.pack(pady=5)
        
        # Descripción
        desc_label = ttk.Label(parent, text="Ingrese la URL de la página web para convertirla a formato Markdown")
        desc_label.pack(pady=5)
        
        # Frame para URL
        url_frame = ttk.Frame(parent)
        url_frame.pack(fill=tk.X, pady=5)
        
        self.web_url_var = tk.StringVar()
        url_entry = ttk.Entry(url_frame, textvariable=self.web_url_var, width=50)
        url_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Barra de progreso
        self.web_progress_var = tk.DoubleVar()
        self.web_progress = ttk.Progressbar(parent, variable=self.web_progress_var, maximum=100)
        self.web_progress.pack(fill=tk.X, pady=10)
        
        # Área de estado
        self.web_status_var = tk.StringVar(value="Listo para convertir")
        web_status_label = ttk.Label(parent, textvariable=self.web_status_var)
        web_status_label.pack(pady=5)
        
        # Frame para botones de acción
        web_button_frame = ttk.Frame(parent)
        web_button_frame.pack(fill=tk.X, pady=5)
        
        # Botón de conversión
        self.web_convert_button = ttk.Button(web_button_frame, text="Convertir a Markdown", 
                                           command=lambda: self.start_conversion("web"))
        self.web_convert_button.pack(side=tk.LEFT, padx=5)
        
        # Botón de cancelación (inicialmente deshabilitado)
        self.web_cancel_button = ttk.Button(web_button_frame, text="Cancelar", 
                                          command=lambda: self.cancel_conversion("web"), state=tk.DISABLED)
        self.web_cancel_button.pack(side=tk.LEFT, padx=5)
        
        # Botón de descarga (inicialmente deshabilitado)
        self.web_download_button = ttk.Button(web_button_frame, text="Descargar Markdown", 
                                            command=lambda: self.download_file("web"), state=tk.DISABLED)
        self.web_download_button.pack(side=tk.RIGHT, padx=5)
        
        # Área de resultados para Web
        result_frame = ttk.LabelFrame(parent, text="Vista previa")
        result_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.web_result_text = scrolledtext.ScrolledText(result_frame, wrap=tk.WORD, height=15)
        self.web_result_text.pack(fill=tk.BOTH, expand=True)
    
    def setup_youtube_tab(self, parent):
        # Título
        title_label = ttk.Label(parent, text="Convertidor de Videos de YouTube a Markdown", font=("Helvetica", 14))
        title_label.pack(pady=5)
        
        # Descripción
        desc_label = ttk.Label(parent, text="Ingrese la URL del video de YouTube para convertirlo a formato Markdown")
        desc_label.pack(pady=5)
        
        # Frame para URL
        yt_url_frame = ttk.Frame(parent)
        yt_url_frame.pack(fill=tk.X, pady=5)
        
        self.yt_url_var = tk.StringVar()
        yt_url_entry = ttk.Entry(yt_url_frame, textvariable=self.yt_url_var, width=50)
        yt_url_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Barra de progreso
        self.yt_progress_var = tk.DoubleVar()
        self.yt_progress = ttk.Progressbar(parent, variable=self.yt_progress_var, maximum=100)
        self.yt_progress.pack(fill=tk.X, pady=10)
        
        # Área de estado
        self.yt_status_var = tk.StringVar(value="Listo para convertir")
        yt_status_label = ttk.Label(parent, textvariable=self.yt_status_var)
        yt_status_label.pack(pady=5)
        
        # Frame para botones de acción
        yt_button_frame = ttk.Frame(parent)
        yt_button_frame.pack(fill=tk.X, pady=5)
        
        # Botón de conversión
        self.yt_convert_button = ttk.Button(yt_button_frame, text="Convertir a Markdown", 
                                          command=lambda: self.start_conversion("youtube"))
        self.yt_convert_button.pack(side=tk.LEFT, padx=5)
        
        # Botón de cancelación (inicialmente deshabilitado)
        self.yt_cancel_button = ttk.Button(yt_button_frame, text="Cancelar", 
                                         command=lambda: self.cancel_conversion("youtube"), state=tk.DISABLED)
        self.yt_cancel_button.pack(side=tk.LEFT, padx=5)
        
        # Botón de descarga (inicialmente deshabilitado)
        self.yt_download_button = ttk.Button(yt_button_frame, text="Descargar Markdown", 
                                         command=lambda: self.download_file("youtube"), state=tk.DISABLED)
        self.yt_download_button.pack(side=tk.RIGHT, padx=5)
        
        # Área de resultados para YouTube
        result_frame = ttk.LabelFrame(parent, text="Vista previa")
        result_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.yt_result_text = scrolledtext.ScrolledText(result_frame, wrap=tk.WORD, height=15)
        self.yt_result_text.pack(fill=tk.BOTH, expand=True)
    
    def browse_file(self):
        filetypes = [("Documentos", " ".join(["*" + ext for ext in get_supported_extensions()])), ("Todos los archivos", "*.*")]
        filename = filedialog.askopenfilename(title="Seleccionar archivo", filetypes=filetypes)
        if filename:
            self.file_path_var.set(filename)
            self.input_file = filename
            
            # Mostrar información del archivo
            file_path = Path(filename)
            file_size = file_path.stat().st_size
            size_mb = file_size / (1024 * 1024)
            
            if size_mb > 5:
                self.status_var.set(f"Archivo grande seleccionado ({size_mb:.1f} MB): {file_path.name}")
                self.time_label.config(text=f"Nota: La conversión puede tardar varios minutos")
            else:
                self.status_var.set(f"Archivo seleccionado ({size_mb:.1f} MB): {file_path.name}")
                self.time_label.config(text="")
    
    def update_progress(self, value):
        """Actualiza la barra de progreso desde un hilo secundario"""
        self.root.after(0, lambda: self.progress_var.set(value))
    
    def conversion_completed(self, success, output_path):
        """Callback llamado cuando se completa la conversión"""
        self.conversion_in_progress = False
        
        if success:
            self.output_file = output_path
            self.root.after(0, lambda: self.status_var.set("Conversión completada exitosamente"))
            self.root.after(0, lambda: self.download_button.config(state=tk.NORMAL))
            self.root.after(0, lambda: messagebox.showinfo("Éxito", "Documento convertido exitosamente"))
        else:
            self.root.after(0, lambda: self.status_var.set("Error en la conversión"))
            self.root.after(0, lambda: self.progress_var.set(0))
            self.root.after(0, lambda: messagebox.showerror("Error", "No se pudo convertir el documento"))
        
        # Restaurar estado de los botones
        self.root.after(0, lambda: self.convert_button.config(state=tk.NORMAL))
        self.root.after(0, lambda: self.cancel_button.config(state=tk.DISABLED))
    
    def start_conversion(self, mode="file"):
        """Inicia el proceso de conversión"""
        if self.conversion_in_progress:
            return
        
        self.current_mode = mode
        
        if mode == "file":
            input_path = self.file_path_var.get()
            if not input_path:
                messagebox.showerror("Error", "Por favor seleccione un archivo para convertir")
                return
            
            # Preparar la ruta de salida temporal
            output_filename = Path(input_path).stem + '.md'
            self.output_file_path = str(self.temp_dir / output_filename)
            
            # Actualizar la interfaz
            self.conversion_in_progress = True
            self.convert_button.config(state=tk.DISABLED)
            self.cancel_button.config(state=tk.NORMAL)
            self.download_button.config(state=tk.DISABLED)
            self.progress_var.set(0)
            self.status_var.set("Iniciando conversión...")
            
            # Iniciar la conversión en un hilo separado
            self.converter.convert_file_async(
                input_path, 
                self.output_file_path, 
                lambda p: self.update_progress(p, mode), 
                lambda s, o: self.conversion_completed(s, o, mode)
            )
            
        elif mode == "web":
            url = self.web_url_var.get()
            if not url:
                messagebox.showerror("Error", "Por favor ingrese una URL para convertir")
                return
            
            # Preparar la ruta de salida temporal
            from urllib.parse import urlparse
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.replace("www.", "")
            path = parsed_url.path.strip("/").replace("/", "_")
            if not path:
                path = "index"
            output_filename = f"{domain}_{path}.md"
            self.output_file_path = str(self.temp_dir / output_filename)
            
            # Actualizar la interfaz
            self.conversion_in_progress = True
            self.web_convert_button.config(state=tk.DISABLED)
            self.web_cancel_button.config(state=tk.NORMAL)
            self.web_download_button.config(state=tk.DISABLED)
            self.web_progress_var.set(0)
            self.web_status_var.set("Iniciando conversión...")
            
            # Iniciar la conversión en un hilo separado
            self.web_converter.convert_url_async(
                url, 
                self.output_file_path, 
                lambda p: self.update_progress(p, mode), 
                lambda s, o: self.conversion_completed(s, o, mode)
            )
            
        elif mode == "youtube":
            url = self.yt_url_var.get()
            if not url:
                messagebox.showerror("Error", "Por favor ingrese una URL de YouTube para convertir")
                return
            
            # Verificar que sea una URL de YouTube
            if "youtube.com" not in url and "youtu.be" not in url:
                messagebox.showerror("Error", "La URL no parece ser de YouTube")
                return
            
            # Preparar la ruta de salida temporal
            from urllib.parse import urlparse
            parsed_url = urlparse(url)
            video_id = parsed_url.query.split('v=')[-1].split('&')[0] if 'v=' in parsed_url.query else parsed_url.path.split('/')[-1]
            output_filename = f"youtube_{video_id}.md"
            self.output_file_path = str(self.temp_dir / output_filename)
            
            # Actualizar la interfaz
            self.conversion_in_progress = True
            self.yt_convert_button.config(state=tk.DISABLED)
            self.yt_cancel_button.config(state=tk.NORMAL)
            self.yt_download_button.config(state=tk.DISABLED)
            self.yt_progress_var.set(0)
            self.yt_status_var.set("Iniciando conversión...")
            
            # Iniciar la conversión en un hilo separado
            self.web_converter.convert_url_async(
                url, 
                self.output_file_path, 
                lambda p: self.update_progress(p, mode), 
                lambda s, o: self.conversion_completed(s, o, mode)
            )
    
    def update_progress(self, progress, mode="file"):
        """Actualiza el progreso en la interfaz"""
        if mode == "file":
            self.progress_var.set(progress)
            if progress < 100:
                self.status_var.set(f"Convirtiendo... {progress:.1f}%")
            else:
                self.status_var.set("Conversión completada")
        elif mode == "web":
            self.web_progress_var.set(progress)
            if progress < 100:
                self.web_status_var.set(f"Convirtiendo... {progress:.1f}%")
            else:
                self.web_status_var.set("Conversión completada")
        elif mode == "youtube":
            self.yt_progress_var.set(progress)
            if progress < 100:
                self.yt_status_var.set(f"Convirtiendo... {progress:.1f}%")
            else:
                self.yt_status_var.set("Conversión completada")
    
    def conversion_completed(self, success, output_path, mode="file"):
        """Maneja la finalización de la conversión"""
        self.conversion_in_progress = False
        
        if mode == "file":
            self.convert_button.config(state=tk.NORMAL)
            self.cancel_button.config(state=tk.DISABLED)
            
            if success:
                self.download_button.config(state=tk.NORMAL)
                self.status_var.set("Conversión completada con éxito")
                messagebox.showinfo("Éxito", "Documento convertido exitosamente")
            else:
                self.status_var.set("Error en la conversión")
                self.progress_var.set(0)
                messagebox.showerror("Error", "No se pudo completar la conversión")
                
        elif mode == "web":
            self.web_convert_button.config(state=tk.NORMAL)
            self.web_cancel_button.config(state=tk.DISABLED)
            
            if success:
                self.web_download_button.config(state=tk.NORMAL)
                self.web_status_var.set("Conversión completada con éxito")
                messagebox.showinfo("Éxito", "Página web convertida exitosamente")
            else:
                self.web_status_var.set("Error en la conversión")
                self.web_progress_var.set(0)
                messagebox.showerror("Error", "No se pudo completar la conversión")
                
        elif mode == "youtube":
            self.yt_convert_button.config(state=tk.NORMAL)
            self.yt_cancel_button.config(state=tk.DISABLED)
            
            if success:
                self.yt_download_button.config(state=tk.NORMAL)
                self.yt_status_var.set("Conversión completada con éxito")
                messagebox.showinfo("Éxito", "Video de YouTube convertido exitosamente")
            else:
                self.yt_status_var.set("Error en la conversión")
                self.yt_progress_var.set(0)
                messagebox.showerror("Error", "No se pudo completar la conversión")
    
    def cancel_conversion(self, mode="file"):
        """Cancela la conversión en curso"""
        if not self.conversion_in_progress:
            return
        
        if mode == "file":
            self.converter.cancel_conversion()
            self.status_var.set("Conversión cancelada")
            self.conversion_in_progress = False
            self.convert_button.config(state=tk.NORMAL)
            self.cancel_button.config(state=tk.DISABLED)
        elif mode == "web":
            self.web_converter.cancel_conversion()
            self.web_status_var.set("Conversión cancelada")
            self.conversion_in_progress = False
            self.web_convert_button.config(state=tk.NORMAL)
            self.web_cancel_button.config(state=tk.DISABLED)
        elif mode == "youtube":
            self.web_converter.cancel_conversion()
            self.yt_status_var.set("Conversión cancelada")
            self.conversion_in_progress = False
            self.yt_convert_button.config(state=tk.NORMAL)
            self.yt_cancel_button.config(state=tk.DISABLED)
    
    def download_file(self, mode="file"):
        """Permite al usuario descargar el archivo convertido"""
        if not self.output_file_path or not Path(self.output_file_path).exists():
            messagebox.showerror("Error", "No hay archivo para descargar")
            return
        
        # Solicitar ubicación para guardar
        save_path = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("Todos los archivos", "*.*")],
            initialfile=Path(self.output_file_path).name
        )
        
        if not save_path:
            return
        
        try:
            # Copiar el archivo
            shutil.copy2(self.output_file_path, save_path)
            
            # Actualizar estado según el modo
            if mode == "file":
                self.status_var.set(f"Archivo guardado en: {save_path}")
            elif mode == "web":
                self.web_status_var.set(f"Archivo guardado en: {save_path}")
            elif mode == "youtube":
                self.yt_status_var.set(f"Archivo guardado en: {save_path}")
                
            messagebox.showinfo("Éxito", f"Archivo guardado en:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar el archivo: {str(e)}")
            logging.error(f"Error al guardar el archivo: {e}")

def main():
    """Función principal que inicia la aplicación GUI"""
    setup_logging()
    root = tk.Tk()
    app = DoclingConverterApp(root)
    root.mainloop()
    
    # Limpiar archivos temporales al salir
    temp_dir = Path("temp_output")
    if temp_dir.exists():
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass

if __name__ == "__main__":
    main()