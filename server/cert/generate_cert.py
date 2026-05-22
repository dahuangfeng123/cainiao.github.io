
from datetime import datetime, timedelta
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import ipaddress

# Generate private key
private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
    backend=default_backend()
)

# Prepare subject and issuer
subject = issuer = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, "CN"),
    x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Beijing"),
    x509.NameAttribute(NameOID.LOCALITY_NAME, "Beijing"),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, "MoringRead"),
    x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
])

# Build certificate
cert = x509.CertificateBuilder().subject_name(
    subject
).issuer_name(
    issuer
).public_key(
    private_key.public_key()
).serial_number(
    x509.random_serial_number()
).not_valid_before(
    datetime.utcnow()
).not_valid_after(
    datetime.utcnow() + timedelta(days=365*10)
).add_extension(
    x509.SubjectAlternativeName([
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
        x509.IPAddress(ipaddress.IPv4Address("192.168.0.109")),
    ]),
    critical=False,
).add_extension(
    x509.KeyUsage(
        digital_signature=True,
        key_encipherment=True,
        key_cert_sign=False,
        key_agreement=False,
        content_commitment=False,
        data_encipherment=False,
        crl_sign=False,
        encipher_only=False,
        decipher_only=False
    ),
    critical=True,
).sign(private_key, hashes.SHA256(), default_backend())

# Save private key
with open("cert/key.pem", "wb") as f:
    f.write(private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ))

# Save certificate
with open("cert/cert.pem", "wb") as f:
    f.write(cert.public_bytes(encoding=serialization.Encoding.PEM))

print("✅ Certificates generated successfully!")
print("📄 cert/cert.pem - Certificate")
print("🔑 cert/key.pem - Private key")
print("\n⚠️ NOTE: You will need to manually trust this certificate in your browser")
print("Or use Chrome flag: --unsafely-treat-insecure-origin-as-secure=http://192.168.0.109:5003")
