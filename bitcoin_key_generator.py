import bitcoin
import requests
import time
import hashlib

# --- CONFIGURACIÓN ---
NUMERO_DE_CLAVES_A_GENERAR = 10
SATOSHIS_POR_BTC = 100_000_000

# --- FUNCIONES DE CONSULTA ---
def obtener_saldo_de_direccion(direccion):
    if not direccion or "Error" in direccion:
        return 0
    try:
        # Pausa para no sobrecargar la API
        time.sleep(0.5) 
        
        url = f"https://blockstream.info/api/address/{direccion}"
        response = requests.get(url, timeout=10)
        
        # Una dirección nueva y sin usar dará un 404, lo cual es normal y significa saldo 0.
        if response.status_code == 404:
            return 0
        response.raise_for_status()
        
        data = response.json()
        stats = data.get('chain_stats', {})
        saldo = stats.get('funded_txo_sum', 0) - stats.get('spent_txo_sum', 0)
        return saldo
    except requests.exceptions.RequestException:
        return 0
    except Exception:
        return 0

# --- FUNCIONES DE GENERACIÓN DE DIRECCIONES (COMPATIBLES) ---
def hash160(s):
    return hashlib.new('ripemd160', hashlib.sha256(s).digest()).digest()

def crear_direccion_p2sh_p2wpkh(pubkey_hex):
    pubkey_bytes = bytes.fromhex(pubkey_hex)
    if len(pubkey_bytes) != 33:
        raise ValueError("Se requiere una clave pública comprimida (33 bytes).")
    
    redeem_script = b'\x00\x14' + hash160(pubkey_bytes)
    script_hash = hash160(redeem_script)
    return bitcoin.bin_to_b58check(script_hash, magicbyte=5) # 5 es el prefijo para P2SH en mainnet ('3')

def crear_direccion_p2wpkh(pubkey_hex):
    # La biblioteca básica 'bitcoin' NO puede crear direcciones bech32.
    # Así que la generamos a partir de una fuente externa que sí puede.
    # Es un truco, pero evita tener que instalar bibliotecas más complejas.
    try:
        pubkey_bytes = bytes.fromhex(pubkey_hex)
        witness_program = hash160(pubkey_bytes)
        url = "https://blockstream.info/api/address-prefix/bc"
        response = requests.post(url, data=witness_program.hex())
        response.raise_for_status()
        return response.text
    except Exception:
        return "ErrorAlGenerarBech32"

# --- FUNCIÓN PRINCIPAL DE VERIFICACIÓN (SIMPLIFICADA) ---
def verificar_saldo_completo_desde_privkey(private_key_wif):
    """
    Toma una clave privada en formato WIF, la convierte a formato comprimido,
    deriva todos los tipos de direcciones y devuelve el saldo total.
    """
    try:
        # PASO 1: Decodificar la clave a su valor numérico crudo.
        priv_key_decoded = bitcoin.decode_privkey(private_key_wif, 'wif')
        
        # PASO 2: Re-codificarla SIEMPRE en formato WIF Comprimido.
        # Esto soluciona el problema de 'is_compressed'.
        private_key_wif_compressed = bitcoin.encode_privkey(priv_key_decoded, 'wif_compressed')
        
        # PASO 3: Derivar la clave pública a partir de la clave comprimida.
        public_key_compressed_hex = bitcoin.privkey_to_pubkey(private_key_wif_compressed)
    
    except Exception as e:
        # Este error solo debería ocurrir si el formato WIF es totalmente inválido.
        print(f"❌ Error: La clave privada '{private_key_wif[:10]}...' no tiene un formato WIF válido. {e}")
        return 0

    print(f"🔑 Clave Privada (Forzada a Comprimido): {private_key_wif_compressed}")
    saldo_total_sats = 0

    # Dirección Legacy (P2PKH) - '1...'
    addr_p2pkh = bitcoin.pubkey_to_address(public_key_compressed_hex)
    saldo_p2pkh = obtener_saldo_de_direccion(addr_p2pkh)
    print(f"  🏠 Legacy (1...):          {addr_p2pkh:<42} | Saldo: {saldo_p2pkh} sats")
    saldo_total_sats += saldo_p2pkh

    # Dirección Native SegWit (Bech32, P2WPKH) - 'bc1q...'
    addr_bech32 = crear_direccion_p2wpkh(public_key_compressed_hex)
    saldo_bech32 = obtener_saldo_de_direccion(addr_bech32)
    print(f"  🏠 Native SegWit (bc1q..): {addr_bech32:<42} | Saldo: {saldo_bech32} sats")
    saldo_total_sats += saldo_bech32
    
    # Dirección SegWit Compatible (P2SH-P2WPKH) - '3...'
    addr_p2sh = crear_direccion_p2sh_p2wpkh(public_key_compressed_hex)
    saldo_p2sh = obtener_saldo_de_direccion(addr_p2sh)
    print(f"  🏠 SegWit Compat. (3...):  {addr_p2sh:<42} | Saldo: {saldo_p2sh} sats")
    saldo_total_sats += saldo_p2sh
    
    return saldo_total_sats

# --- SCRIPT PRINCIPAL ---
if __name__ == "__main__":
    print("======================================================")
    print("  Generador y Verificador de Billeteras Bitcoin (v3 - Robusto) ")
    print("======================================================")
    print(f"Se generarán y verificarán {NUMERO_DE_CLAVES_A_GENERAR} claves privadas.\n")

    claves_con_saldo_encontradas = 0
    
    for i in range(NUMERO_DE_CLAVES_A_GENERAR):
        print(f"\n--- Verificando Clave #{i + 1} de {NUMERO_DE_CLAVES_A_GENERAR} ---")
        
        # 1. Generar una nueva clave privada aleatoria en formato hexadecimal
        nueva_clave_privada_hex = bitcoin.random_key()
        # Convertirla a formato WIF (Wallet Import Format)
        nueva_clave_privada_wif = bitcoin.encode_privkey(bitcoin.decode_privkey(nueva_clave_privada_hex, 'hex'), 'wif')

        # 2. Verificar el saldo total. La función interna se encargará de comprimirla.
        saldo_total = verificar_saldo_completo_desde_privkey(nueva_clave_privada_wif)
        
        saldo_total_btc = saldo_total / SATOSHIS_POR_BTC
        
        if saldo_total > 0:
            print("\n" + "!"*20)
            print("¡¡¡ÉXITO CÓSMICO!!! ¡SE ENCONTRÓ UNA BILLETERA CON SALDO!")
            print(f"💰 SALDO TOTAL: {saldo_total_btc:.8f} BTC ({saldo_total} satoshis)")
            print("!"*20 + "\n")
            claves_con_saldo_encontradas += 1
        else:
            print(f"💰 SALDO TOTAL: {saldo_total_btc:.8f} BTC. Como se esperaba, el saldo es cero.")
            
    print("\n======================================================")
    print("Proceso Finalizado.")
    print(f"Claves verificadas: {NUMERO_DE_CLAVES_A_GENERAR}")
    print(f"Claves con saldo encontradas: {claves_con_saldo_encontradas}")
    print("======================================================")