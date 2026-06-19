#!/usr/bin/env python3
"""Emisor: captura vídeo y lo envía por TCP a receptores.

Uso:
    python emisor.py [HOST] [PUERTO] [--test] [--cam CAM_INDEX]

Ejemplo:
    python emisor.py 0.0.0.0 9999
"""
import socket
import struct
import cv2
import numpy as np
import time
import sys
import argparse

# Configuración de red por defecto
HOST = '0.0.0.0'  # Escuchar en todas las interfaces
PUERTO = 9999     # Puerto a usar (puede cambiarse)

def iniciar_emisor(host=HOST, puerto=PUERTO, test_mode=False, cam_index=0):
    camara = None
    if not test_mode:
        # Crear objeto de captura de video (cámara por defecto o la especificada)
        camara = cv2.VideoCapture(cam_index)
        if not camara.isOpened():
            print(f"Error: no se pudo abrir la cámara (índice {cam_index}).")
            return
        print(f"[OK] Cámara abierta (índice {cam_index})")
    else:
        print("[OK] Modo de prueba activo (generando marcos sintéticos)")

    # Crear socket TCP y preparar para aceptar conexiones de receptores
    socket_emisor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    socket_emisor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    socket_emisor.bind((host, puerto))
    socket_emisor.listen(1)
    print(f"Escuchando en {host}:{puerto} ...")

    try:
        while True:
            # Esperar a que un receptor se conecte
            conexion, direccion = socket_emisor.accept()
            print(f"Receptor conectado desde {direccion}")
            try:
                # Bucle principal: capturar/generar y enviar marcos continuamente
                while True:
                    if test_mode:
                        # Generar marco sintético (fondo negro con texto y figura en movimiento)
                        fotograma = np.zeros((480, 640, 3), dtype=np.uint8)
                        timestamp = time.strftime("%H:%M:%S")
                        milisegundos = int((time.time() - int(time.time())) * 1000)
                        texto = f"TEST STREAM: {timestamp}.{milisegundos:03d}"
                        
                        # Dibujar un círculo en movimiento
                        angulo = time.time() * 2
                        cx = int(320 + 150 * np.cos(angulo))
                        cy = int(240 + 100 * np.sin(angulo))
                        cv2.circle(fotograma, (cx, cy), 40, (0, 0, 255), -1)
                        
                        # Agregar el texto
                        cv2.putText(fotograma, texto, (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                        ret = True
                    else:
                        ret, fotograma = camara.read()
                        if not ret:
                            # Si falla la lectura, esperar un momento y reintentar
                            time.sleep(0.1)
                            continue

                    # Codificar el fotograma a JPEG para reducir tamaño
                    # El tercer parámetro es la calidad JPEG (0-100)
                    parametros_codificacion = [int(cv2.IMWRITE_JPEG_QUALITY), 80]
                    resultado, imagen_codificada = cv2.imencode('.jpg', fotograma, parametros_codificacion)
                    if not resultado:
                        # Si la codificación falla, saltar este fotograma
                        continue

                    datos = imagen_codificada.tobytes()
                    # Enviar primero 4 bytes con el tamaño del bloque (big-endian)
                    tamaño = struct.pack('!I', len(datos))
                    try:
                        # Enviar tamaño + datos del fotograma
                        conexion.sendall(tamaño + datos)
                    except (BrokenPipeError, ConnectionResetError):
                        # El receptor se desconectó inesperadamente
                        print("Receptor desconectado.")
                        break
                    # Pequeña pausa para evitar saturar la red/cpu y regular FPS
                    time.sleep(0.033)  # ~30 FPS
            except Exception as e:
                # Cualquier excepción del bucle de conexión se registra
                print(f"Error durante la transmisión: {e}")
            finally:
                # Cerrar la conexión actual y volver a esperar otro receptor
                try:
                    conexion.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                conexion.close()
                print("Conexión cerrada, esperando nuevo receptor...")
    except KeyboardInterrupt:
        # Permitir terminar el emisor con Ctrl+C
        print("\nEmisor detenido por el usuario.")
    finally:
        # Liberar recursos: cámara y socket del emisor
        if camara is not None:
            camara.release()
        socket_emisor.close()
        print("Recursos liberados, emisor finalizado.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Emisor de Video por TCP")
    parser.add_argument('host', nargs='?', default=HOST, help="Host a escuchar")
    parser.add_argument('puerto', nargs='?', type=int, default=PUERTO, help="Puerto a escuchar")
    parser.add_argument('--test', action='store_true', help="Ejecutar en modo de prueba (sin cámara)")
    parser.add_argument('--cam', type=int, default=0, help="Índice de la cámara a usar")
    
    args = parser.parse_args()
    iniciar_emisor(args.host, args.puerto, test_mode=args.test, cam_index=args.cam)
