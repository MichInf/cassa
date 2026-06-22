# Stampante ESC/POS — Configurazione USB

**Dispositivo:** VID=`0x0416` PID=`0x5011`  
**Libreria:** `python-escpos` + `pyusb`

---

## Installazione

```bash
python3 -m venv ~/venv-escpos
source ~/venv-escpos/bin/activate
pip install python-escpos pyusb
```

## Permessi USB (una volta sola)

```bash
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="0416", ATTRS{idProduct}=="5011", MODE="0666"' \
  | sudo tee /etc/udev/rules.d/99-escpos.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

## Connessione

```python
from escpos.printer import Usb

p = Usb(0x0416, 0x5011, in_ep=0x82, out_ep=0x01)
```
