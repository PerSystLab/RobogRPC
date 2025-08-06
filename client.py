import grpc
import time
import serial

import hand_control_pb2
import hand_control_pb2_grpc

GLOVE_SERIAL_PORT = '/tmp/glove_read'
GLOVE_BAUD_RATE = 115200
SERVER_ADDRESS = 'localhost'
SERVER_PORT = 50051

def parse_hand_data(line):
    try:
        parts = line.split(',')
        if len(parts) == 5:
            finger_values = list(map(int, parts))
            return finger_values
    except (ValueError, IndexError):
        pass
    return None

def generate_hand_data(serial_port):
    message_count = 0
    start_time = time.time()
    
    while True:
        try:
            line = serial_port.readline().decode('utf-8').strip()
            if not line:
                continue
            
            finger_values = parse_hand_data(line)
            if finger_values:
                message_count += 1
                
                # Rate hesapla
                elapsed = time.time() - start_time
                rate = message_count / elapsed if elapsed > 0 else 0
                
                if message_count % 50 == 0:
                    print(f"CLIENT #{message_count:04d} | {rate:.1f} msg/s | Parmaklar: {finger_values}")
                
                # Timestamp ekle
                timestamp_ms = int(time.time() * 1000)
                yield hand_control_pb2.HandData(finger_values=finger_values, timestamp_ms=timestamp_ms)
            else:
                print(f"Geçersiz veri: {line}")
                
        except (UnicodeDecodeError, ValueError) as e:
            print(f"Parse hatası: {e}")
            continue
        except serial.SerialException as e:
            print(f"Serial hatası: {e}")
            break

def create_grpc_channel():
    options = [
        ('grpc.keepalive_time_ms', 10000),
        ('grpc.keepalive_timeout_ms', 5000),
        ('grpc.keepalive_permit_without_calls', True)
    ]
    return grpc.insecure_channel(f'{SERVER_ADDRESS}:{SERVER_PORT}', options=options)

def main():
    print(f"Client başlatılıyor...")
    print(f"Eldiven portu: {GLOVE_SERIAL_PORT}")
    print(f"Server: {SERVER_ADDRESS}:{SERVER_PORT}")
    print("Server hazır olduğunda Enter'a basın:")
    input()
    
    try:
        glove_serial = serial.Serial(GLOVE_SERIAL_PORT, GLOVE_BAUD_RATE)
        print(f"Eldiven bağlandı: {GLOVE_SERIAL_PORT}")
    except serial.SerialException as e:
        print(f"Eldiven bağlantı hatası: {e}")
        return

    with create_grpc_channel() as channel:
        stub = hand_control_pb2_grpc.HandControllerStub(channel)
        
        try:
            grpc.channel_ready_future(channel).result(timeout=10)
            print("Server'a bağlandı")
        except grpc.FutureTimeoutError:
            print("Server bağlantısı timeout")
            return
        
        try:
            start_time = time.time()
            hand_data_stream = generate_hand_data(glove_serial)
            response = stub.StreamHandData(hand_data_stream)
            end_time = time.time()
            
            print(f"Tamamlandı. Süre: {end_time - start_time:.2f}s")
        
        except grpc.RpcError as e:
            print(f"gRPC hatası: {e.code()}")
        except Exception as e:
            print(f"Hata: {e}")
        finally:
            if glove_serial.is_open:
                glove_serial.close()
                print("Serial port kapatıldı")

if __name__ == '__main__':
    main()
