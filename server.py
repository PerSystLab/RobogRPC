"""
gRPC Server - Hand Control System
Eldiven verilerini alır ve robot'a servo komutları gönderir.
"""

import grpc
from concurrent import futures
import time
import serial

import hand_control_pb2
import hand_control_pb2_grpc

# Konfigürasyon
ROBOT_SERIAL_PORT = '/tmp/robot_write'  # Simülasyon için
ROBOT_BAUD_RATE = 9600              # lehand.ino ile aynı hız
GRPC_PORT = 50051
MAX_WORKERS = 10

def map_sensor_to_servo(sensor_value, in_min=0, in_max=1023, out_min=500, out_max=2500):
    """Sensör değerini servo PWM değerine dönüştür."""
    sensor_value = max(in_min, min(sensor_value, in_max))
    return (sensor_value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

def format_servo_command(servo_values):
    """Servo değerlerini Arduino formatına çevir."""
    return ",".join(map(str, servo_values)) + "\n"

class HandControllerServicer(hand_control_pb2_grpc.HandControllerServicer):
    """gRPC service implementasyonu."""
    
    def __init__(self):
        self.robot_serial = None
        self.start_time = None
        self.message_count = 0
        self.total_latency = 0
        
        self._initialize_serial_connection()
    
    def _initialize_serial_connection(self):
        """Robot Arduino'su ile bağlantıyı kur."""
        try:
            self.robot_serial = serial.Serial(ROBOT_SERIAL_PORT, ROBOT_BAUD_RATE, timeout=1)
            print(f"Robot Arduino'suna bağlanıldı: {ROBOT_SERIAL_PORT}")
        except serial.SerialException as e:
            print(f"Robot Arduino'suna bağlanılamadı: {e}")
    
    def StreamHandData(self, request_iterator, context):
        """Eldiven veri akışını işle."""
        self.start_time = time.time()
        print("⏳ Server hazır. Client'dan veri akışı bekleniyor...")
        print("Client veri akışı başladı")
        
        try:
            for hand_data in request_iterator:
                self._process_hand_data(hand_data)
                
        except grpc.RpcError as e:
            print(f"gRPC hatası: {e}")
        except Exception as e:
            print(f"Beklenmeyen hata: {e}")
        
        self._log_final_statistics()
        return hand_control_pb2.Ack(success=True)
    
    def _process_hand_data(self, hand_data):
        """Tek bir eldiven mesajını işle."""
        message_start_time = time.time()
        self.message_count += 1
        
        # Sensör değerlerini servo komutlarına dönüştür
        servo_commands = [
            int(map_sensor_to_servo(val, 0, 1023, 500, 2500)) 
            for val in hand_data.finger_values
        ]
        
        # Robot'a servo komutlarını gönder
        if self.robot_serial and self.robot_serial.is_open:
            command_string = format_servo_command(servo_commands)
            self.robot_serial.write(command_string.encode('utf-8'))
        
        # Performans metriklerini hesapla ve göster
        self._update_metrics(message_start_time, servo_commands)
    
    def _update_metrics(self, message_start_time, servo_commands):
        """Performans metriklerini güncelle."""
        processing_time = (time.time() - message_start_time) * 1000  # ms
        self.total_latency += processing_time
        avg_latency = self.total_latency / self.message_count
        
        total_time = time.time() - self.start_time
        throughput = self.message_count / total_time
        
        if self.message_count % 50 == 0:
            print(f"SERVER: #{self.message_count:04d} | Latency: {processing_time:.1f}ms | Ort: {avg_latency:.1f}ms | Servolar: {servo_commands}")
    
    def _log_final_statistics(self):
        """Final istatistikleri göster."""
        if self.message_count > 0:
            total_time = time.time() - self.start_time
            avg_latency = self.total_latency / self.message_count
            throughput = self.message_count / total_time
            
            print(f"Veri akışı sona erdi - Toplam: {self.message_count} mesaj, "
                  f"Süre: {total_time:.2f}s, Ortalama latency: {avg_latency:.2f}ms, "
                  f"Throughput: {throughput:.2f} msg/s")

def serve():
    """gRPC server'ı başlat."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=MAX_WORKERS))
    hand_control_pb2_grpc.add_HandControllerServicer_to_server(HandControllerServicer(), server)
    server.add_insecure_port(f'[::]:{GRPC_PORT}')
    server.start()
    
    print(f"gRPC Server başlatıldı - Port: {GRPC_PORT}")
    print(f"gRPC Server çalışıyor - Port: {GRPC_PORT}")
    print("Server hazır! Artık Client'ı başlatabilirsiniz")
    print("Client bağlantısı bekleniyor...")
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        print("Server kapatılıyor...")
        server.stop(0)

if __name__ == '__main__':
    serve()
