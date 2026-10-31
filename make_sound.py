import wave
import math
import struct

def generate_ping_file(filename="ping.wav", duration=0.1, frequency=800.0, sample_rate=44100):
    num_samples = int(duration * sample_rate)
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        for i in range(num_samples):
            t = float(i) / sample_rate
            value = math.sin(2 * math.pi * frequency * t)
            decay = math.exp(-6 * t / duration) 
            packed_value = struct.pack('<h', int(value * decay * 32767))
            wav_file.writeframesraw(packed_value)

if __name__ == '__main__':
    generate_ping_file()
    print("Fichier 'ping.wav' généré avec succès !")