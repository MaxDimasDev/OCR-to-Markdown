import logging
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
import shutil
import os

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
        pass
    
    def convert_file(self, input_path, output_path=None):
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
            
            logging.info(f"Convirtiendo: {input_path}")
            result = subprocess.run(["docling", input_path, "--output", output_path], 
                                   capture_output=True, text=True)
            
            if result.returncode == 0:
                logging.info(f"Archivo convertido exitosamente: {input_path} -> {output_path}")
                return True
            else:
                logging.error(f"Error al convertir {input_path}: {result.stderr}")
                return False
            
        except Exception as e:
            logging.error(f"Error al convertir {input_path}: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def convert_directory(self, input_dir, output_dir):
        ensure_directory_exists(output_dir)
        
        input_path = Path(input_dir)
        stats = {
            'total_files': 0,
            'converted': 0,
            'failed': 0,
            'skipped': 0
        }
        
        supported_extensions = get_supported_extensions()
        
        for file_path in input_path.iterdir():
            if file_path.is_file():
                stats['total_files'] += 1
                
                if file_path.suffix.lower() in supported_extensions:
                    output_filename = file_path.stem + '.md'
                    output_path = str(Path(output_dir) / output_filename)
                    if self.convert_file(str(file_path), output_path):
                        stats['converted'] += 1
                    else:
                        stats['failed'] += 1
                else:
                    stats['skipped'] += 1
                    logging.info(f"Archivo omitido (formato no soportado): {file_path.name}")
        
        return stats

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
        
        # Botón de conversión
        convert_button = ttk.Button(main_frame, text="Convertir a Markdown", command=self.convert_file)
        convert_button.pack(pady=10)
        
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
    
    def browse_file(self):
        filetypes = [("Documentos", " ".join(["*" + ext for ext in get_supported_extensions()])), ("Todos los archivos", "*.*")]
        filename = filedialog.askopenfilename(title="Seleccionar archivo", filetypes=filetypes)
        if filename:
            self.file_path_var.set(filename)
            self.input_file = filename
            self.status_var.set(f"Archivo seleccionado: {Path(filename).name}")
    
    def convert_file(self):
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
        self.progress_var.set(50)
        self.root.update()
        
        # Realizar la conversión
        success = self.converter.convert_file(str(input_path), output_path)
        
        if success:
            self.output_file = output_path
            self.status_var.set("Conversión completada exitosamente")
            self.progress_var.set(100)
            self.download_button.config(state=tk.NORMAL)
            messagebox.showinfo("Éxito", "Documento convertido exitosamente")
        else:
            self.status_var.set("Error en la conversión")
            self.progress_var.set(0)
            messagebox.showerror("Error", "No se pudo convertir el documento")
    
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