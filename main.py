import logging
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
import shutil
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

# Funciones de utilidad
def get_supported_extensions():
    return [
        '.pdf', '.docx', '.pptx', '.html', '.txt',
        '.csv', '.xlsx', '.ppt', '.doc', '.xml'
    ]

def ensure_directory_exists(directory):
    Path(directory).mkdir(parents=True, exist_ok=True)

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
        self.root.geometry("600x400")
        self.root.resizable(True, True)
        
        self.converter = DoclingToMarkdownConverter()
        self.setup_ui()
        self.temp_dir = Path("temp_output")
        self.input_file = None
        self.output_file = None
        self.conversion_in_progress = False
        
    def setup_ui(self):
        # Crear frame principal
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        title_label = ttk.Label(main_frame, text="Convertidor de Documentos a Markdown", font=("Helvetica", 16))
        title_label.pack(pady=10)
        
        # Descripción
        desc_label = ttk.Label(main_frame, text="Seleccione un archivo para convertirlo a formato Markdown")
        desc_label.pack(pady=5)
        
        # Frame para selección de archivo
        file_frame = ttk.Frame(main_frame)
        file_frame.pack(fill=tk.X, pady=10)
        
        self.file_path_var = tk.StringVar()
        file_entry = ttk.Entry(file_frame, textvariable=self.file_path_var, width=50)
        file_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        browse_button = ttk.Button(file_frame, text="Examinar", command=self.browse_file)
        browse_button.pack(side=tk.RIGHT, padx=5)
        
        # Formatos soportados
        formats_text = "Formatos soportados: " + ", ".join(get_supported_extensions())
        formats_label = ttk.Label(main_frame, text=formats_text)
        formats_label.pack(pady=5)
        
        # Frame para botones de acción
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        # Botón de conversión
        self.convert_button = ttk.Button(button_frame, text="Convertir a Markdown", command=self.start_conversion)
        self.convert_button.pack(side=tk.LEFT, padx=5)
        
        # Botón de cancelación (inicialmente deshabilitado)
        self.cancel_button = ttk.Button(button_frame, text="Cancelar", command=self.cancel_conversion, state=tk.DISABLED)
        self.cancel_button.pack(side=tk.LEFT, padx=5)
        
        # Barra de progreso
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress.pack(fill=tk.X, pady=10)
        
        # Área de estado
        self.status_var = tk.StringVar(value="Listo para convertir")
        status_label = ttk.Label(main_frame, textvariable=self.status_var)
        status_label.pack(pady=5)
        
        # Botón de descarga (inicialmente deshabilitado)
        self.download_button = ttk.Button(main_frame, text="Descargar Markdown", command=self.download_file, state=tk.DISABLED)
        self.download_button.pack(pady=10)
        
        # Información de tiempo estimado
        self.time_label = ttk.Label(main_frame, text="")
        self.time_label.pack(pady=5)
    
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
    
    def start_conversion(self):
        """Inicia la conversión de forma asíncrona"""
        if not self.file_path_var.get():
            messagebox.showerror("Error", "Por favor seleccione un archivo para convertir")
            return
        
        input_path = Path(self.file_path_var.get())
        if not input_path.exists():
            messagebox.showerror("Error", f"El archivo no existe: {input_path}")
            return
        
        if input_path.suffix.lower() not in get_supported_extensions():
            messagebox.showerror("Error", f"Formato no soportado: {input_path.suffix}")
            return
        
        # Crear directorio temporal para la salida
        ensure_directory_exists(self.temp_dir)
        output_filename = input_path.stem + '.md'
        output_path = str(self.temp_dir / output_filename)
        
        # Actualizar UI
        self.status_var.set("Convirtiendo documento...")
        self.progress_var.set(0)
        self.conversion_in_progress = True
        
        # Actualizar estado de los botones
        self.convert_button.config(state=tk.DISABLED)
        self.cancel_button.config(state=tk.NORMAL)
        self.download_button.config(state=tk.DISABLED)
        
        # Iniciar conversión asíncrona
        self.converter.convert_file_async(
            str(input_path), 
            output_path, 
            progress_callback=self.update_progress,
            completion_callback=self.conversion_completed
        )
    
    def cancel_conversion(self):
        """Cancela la conversión en curso"""
        if self.conversion_in_progress:
            self.converter.cancel_conversion()
            self.status_var.set("Conversión cancelada")
            self.progress_var.set(0)
            self.conversion_in_progress = False
            self.convert_button.config(state=tk.NORMAL)
            self.cancel_button.config(state=tk.DISABLED)
    
    def download_file(self):
        if not self.output_file or not Path(self.output_file).exists():
            messagebox.showerror("Error", "No hay archivo para descargar")
            return
        
        # Solicitar ubicación para guardar
        save_path = filedialog.asksaveasfilename(
            title="Guardar archivo Markdown",
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("Todos los archivos", "*.*")],
            initialfile=Path(self.output_file).name
        )
        
        if save_path:
            try:
                shutil.copy2(self.output_file, save_path)
                self.status_var.set(f"Archivo guardado en: {save_path}")
                messagebox.showinfo("Éxito", f"Archivo guardado exitosamente en:\n{save_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Error al guardar el archivo: {str(e)}")

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