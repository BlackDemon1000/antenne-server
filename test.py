#!/usr/bin/env python3
"""
Automatisiertes Website-Testing mit Chromium auf Linux
Für autorisierte Cybersicherheitstests
"""

import time
import logging
import sys
import os
import random
import pytz
from tempfile import mkdtemp
from datetime import datetime, timedelta
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.common.exceptions import UnexpectedAlertPresentException

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ChromeBotTester:
    def __init__(self, chromedriver_path=None):
        if chromedriver_path is None:
            chromedriver_path = os.path.join(sys._MEIPASS, "chromedriver") if hasattr(sys, '_MEIPASS') else "/usr/bin/chromedriver"
        self.chromedriver_path = chromedriver_path
        self.driver = None
        self.successful_attempts = 0
        self.failed_attempts = 0
        self.total_attempts = 0
        self.user_agents = self.load_user_agents()

    def voting_allowed_now(self):
        """Prüft, ob aktuell zwischen 5 und 22 Uhr UTC+1 ist"""
        try:
            utc_plus_1 = pytz.timezone('Europe/Berlin')  # UTC+1 mit Sommerzeit korrekt
            now = datetime.now(utc_plus_1)
            if 5 <= now.hour < 22:
                return True
            else:
                logger.info(f"Aktuelle Zeit ({now.strftime('%H:%M')}) liegt außerhalb des Voting-Fensters.")
                return False
        except Exception as e:
            logger.error(f"Fehler bei Zeitprüfung: {e}")
            return False


    def load_user_agents(self):
        """Lädt User-Agents aus der useragents.txt-Datei"""
        if hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        user_agents_file = os.path.join(base_path, "useragents.txt")
        try:
            with open(user_agents_file, 'r', encoding='utf-8') as file:
                user_agents = [line.strip() for line in file if line.strip()]
            if not user_agents:
                logger.error("Die Datei useragents.txt ist leer oder enthält keine gültigen User-Agents.")
                sys.exit(1)
            logger.info(f"{len(user_agents)} User-Agents aus {user_agents_file} geladen.")
            return user_agents
        except FileNotFoundError:
            logger.error(f"Die Datei {user_agents_file} wurde nicht gefunden.")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Fehler beim Laden der User-Agents aus {user_agents_file}: {e}")
            sys.exit(1)

    def get_available_user_agent(self):
        """Wählt einen zufälligen User-Agent aus der geladenen Liste"""
        if not self.user_agents:
            logger.error("Keine User-Agents verfügbar.")
            return "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
        return random.choice(self.user_agents)

    def setup_chrome_browser(self):
        """Chromium mit zufälligem User-Agent und 'I still don't care about cookies' starten"""
        try:
            options = Options()
            options.binary_location = "/usr/bin/chromium"
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument(f"user-agent={self.get_available_user_agent()}")
            options.add_argument("--lang=de-DE")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-web-security")
            options.add_argument("--disable-site-isolation-trials")
            options.add_argument("--disable-features=IsolateOrigins,site-per-process")
            options.add_argument("--disable-webrtc")
            options.add_argument("--disable-canvas-aa")

            # Lade 'I still don't care about cookies'-Erweiterung
            if hasattr(sys, '_MEIPASS'):
                extension_path = os.path.join(sys._MEIPASS, "idcac_extension")
            else:
                extension_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "idcac_extension")
            if os.path.exists(extension_path):
                options.add_argument(f"--load-extension={extension_path}")
                logger.info(f"'I still don't care about cookies'-Erweiterung geladen aus: {extension_path}")
            else:
                logger.warning(f"Erweiterungsverzeichnis {extension_path} nicht gefunden. Fahre ohne Erweiterung fort.")

            # Temporäres Profil erstellen
            temp_dir = mkdtemp()
            options.add_argument(f"--user-data-dir={temp_dir}")

            service = Service(self.chromedriver_path)
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.set_page_load_timeout(30)
            logger.info("Chromium-Browser erfolgreich gestartet")
            return True
        except Exception as e:
            logger.error(f"Fehler beim Starten des Browsers: {e}")
            return False

    def dismiss_cookie_banner(self):
        """Fallback: Cookie-Banner manuell wegklicken, falls Erweiterung fehlschlägt"""
        logger.info("Überprüfe auf Cookie-Banner (Fallback)...")
        xpaths = [
            "//button[@data-testid='uc-accept-all-button']",
            "//button[@data-testid='uc-deny-all-button']",
            "//button[@data-testid='uc-save-button']",
            "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'akzeptieren')]",
            "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'ablehnen')]",
            "//*[contains(text(), 'Alle akzeptieren')]",
            "//*[contains(text(), 'Akzeptieren')]",
            "//*[contains(text(), 'Einverstanden')]",
            "//*[contains(text(), 'Zustimmen')]",
            "//button[contains(@id, 'accept')]",
            "//button[contains(@class, 'cookie')]",
            "//div[contains(@class, 'cookie')]//button",
            "//a[contains(text(), 'Akzeptieren')]"
        ]
        try:
            WebDriverWait(self.driver, 3).until(
                EC.presence_of_element_located((By.XPATH, "//div[@id='usercentrics-root']"))
            )
            logger.info("Usercentrics-Cookie-Banner erkannt. Versuche manuelles Schließen.")
            for path in xpaths:
                try:
                    btn = self.driver.find_element(By.XPATH, path)
                    if btn and btn.is_displayed() and btn.is_enabled():
                        self.driver.execute_script("arguments[0].click();", btn)
                        logger.info("Cookie-Banner geschlossen mit XPath: %s", path)
                        time.sleep(0.15)
                        return True
                except (NoSuchElementException, TimeoutException):
                    continue
            logger.warning("Kein passender Cookie-Banner-Button gefunden.")
            return False
        except TimeoutException:
            logger.info("Kein Cookie-Banner gefunden (Timeout).")
            return True
        except Exception as e:
            logger.error(f"Fehler beim Schließen des Cookie-Banners: {e}")
            return False

    def wait_for_element(self, locator_type, locator_value, timeout=20):
        """Auf Element warten"""
        try:
            wait = WebDriverWait(self.driver, timeout)
            by = By.XPATH if locator_type == 'xpath' else By.ID
            return wait.until(EC.element_to_be_clickable((by, locator_value)))
        except TimeoutException:
            logger.warning(f"Element nicht gefunden: {locator_value} (Timeout: {timeout}s)")
            return None

    def click_element(self, locator_type, locator_value, timeout=10):
        """Element klicken"""
        element = self.wait_for_element(locator_type, locator_value, timeout)
        if element:
            try:
                self.driver.execute_script("arguments[0].click();", element)
                logger.info(f"Element geklickt: {locator_value}")
                time.sleep(0.25)
                return True
            except Exception as e:
                logger.error(f"Fehler beim Klicken auf {locator_value}: {e}")
                return False
        return False

    def check_error_message(self):
        """Prüfen ob Fehlermeldung angezeigt wird"""
        try:
            error_element = self.driver.find_element(
                By.XPATH,
                "/html/body/div[1]/div[2]/main/div[2]/div/div[1]/form/fieldset/div[1]/div/div[2]/h3"
            )
            if error_element.text == "Fehler":
                logger.warning("Fehler-Meldung erkannt")
                return True
        except NoSuchElementException:
            pass
        return False

    def evade_bot_detection(self):
        """Anti-Bot-Maßnahmen für Chromium"""
        try:
            self.driver.execute_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                navigator.plugins = [1, 2, 3];
                Object.defineProperty(navigator, 'languages', {get: () => ['de-DE', 'de']});
                Object.defineProperty(navigator, 'platform', {get: () => 'Linux x86_64'});
            """)
            logger.info("Anti-Bot-Erkennung: navigator.webdriver & Plugins gefälscht")
        except Exception as e:
            logger.warning(f"Anti-Bot-Vermeidung fehlgeschlagen: {e}")

    def perform_test_sequence(self):
        """Führt die komplette Testsequenz aus"""
        try:
            self.total_attempts += 1
            logger.info(f"Versuch #{self.total_attempts} gestartet")
            self.driver.delete_all_cookies()

            # Zur Website navigieren
            url = "https://www.antenne.de/programm/aktionen/die-antenne-bayern-schulhof-gigs/schulen/13248-gymnasium-markt-indersdorf"
            self.driver.get(url)
            self.driver.execute_script("document.body.style.zoom='30%'")
            logger.info("Zoom auf 30% gesetzt")
            self.evade_bot_detection()

            # Warten, bis die Seite vollständig geladen ist
            WebDriverWait(self.driver, 10).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            logger.info(f"Website geladen: {url}")

            # Fallback: Cookie-Banner manuell behandeln, falls Erweiterung fehlschlägt
            if not self.dismiss_cookie_banner():
                logger.warning("Fallback: Cookie-Banner konnte nicht geschlossen werden.")

            # 1. Ersten Button klicken (voteIntendButton)
            if not self.click_element("id", "voteIntendButton", 4):
                logger.error("Schritt 1 fehlgeschlagen: voteIntendButton nicht gefunden")
                self.failed_attempts += 1
                return False

            # 2. Zweiten Button klicken
            if not self.click_element("xpath", "/html/body/div[1]/div[2]/main/div[2]/div/div[1]/form/fieldset/div/aside/label", 2):
                logger.error("Schritt 2 fehlgeschlagen: Zweiter Button nicht gefunden")
                # self.failed_attempts += 1
                # return False

            # 3. Dritten Button klicken
            if not self.click_element("xpath", "/html/body/div[1]/div[2]/main/div[2]/div/div[1]/form/fieldset/div/div/div/div[1]/div/div/div/button", 4):
                logger.error("Schritt 3 fehlgeschlagen: Dritter Button nicht gefunden")
                self.failed_attempts += 1
                return False

            # 4. Voting Button klicken
            if not self.click_element("id", "votingButton", 30):
                logger.error("Schritt 4 fehlgeschlagen: votingButton nicht gefunden")
                self.failed_attempts += 1
                return False

            # 5. Auf Fehler prüfen
            if self.check_error_message():
                logger.warning("Fehler-Meldung erkannt - Versuch nicht gezählt")
                self.failed_attempts += 1
                return False

            # Erfolg
            self.successful_attempts += 1
            logger.info("Versuch erfolgreich abgeschlossen!")
            response = requests.get("https://counterantenne.bergerhq.de/api/increment", allow_redirects=True)
            return True

        except Exception as e:
            logger.error(f"Fehler in Testsequenz: {e}")
            self.failed_attempts += 1
            return False

    def run_test_loop(self, max_attempts=None, delay_between_attempts=5):
        """Haupttest-Loop"""
        start_time = time.time()

        if max_attempts is None:
            logger.info("Starte unbegrenzten Test-Loop")
        else:
            logger.info(f"Starte Test-Loop mit maximal {max_attempts} Versuchen")

        if not self.setup_chrome_browser():
            logger.error("Konnte Chromium-Browser nicht starten")
            return

        try:
            attempt = 0
            while max_attempts is None or attempt < max_attempts:
                attempt += 1
                logger.info(f"\n--- Durchlauf {attempt}/{max_attempts if max_attempts else 'unbegrenzt'} ---")

                if not self.voting_allowed_now():
                    logger.info("Voting aktuell nicht erlaubt. Warte 5 Minuten...")
                    time.sleep(300)
                    continue

                if max_attempts is None:
                    logger.info(f"\n--- Durchlauf {attempt} (unbegrenzt) ---")
                else:
                    logger.info(f"\n--- Durchlauf {attempt}/{max_attempts} ---")

                # Neuer Browser für jeden Versuch
                if attempt > 1:
                    self.cleanup()
                    self.setup_chrome_browser()

                # Testsequenz ausführen
                success = self.perform_test_sequence()

                # Statistiken ausgeben
                elapsed_minutes = (time.time() - start_time) / 60
                if elapsed_minutes > 0:
                    success_per_minute = self.successful_attempts / elapsed_minutes
                    logger.info(f"Erfolgsrate pro Minute: {success_per_minute:.2f}")

                success_rate = (self.successful_attempts / self.total_attempts) * 100
                logger.info(f"Erfolgreiche Versuche: {self.successful_attempts}")
                logger.info(f"Fehlgeschlagene Versuche: {self.failed_attempts}")
                logger.info(f"Erfolgsrate: {success_rate:.1f}%")

                #time.sleep(delay_between_attempts)

        except KeyboardInterrupt:
            logger.info("Test durch Benutzer abgebrochen")

        finally:
            self.cleanup()

    def cleanup(self):
        """Aufräumen"""
        if self.driver:
            self.driver.quit()
        logger.info("Browser geschlossen")

        # Finale Statistiken
        logger.info("\n=== FINALE STATISTIKEN ===")
        logger.info(f"Gesamte Versuche: {self.total_attempts}")
        logger.info(f"Erfolgreiche Versuche: {self.successful_attempts}")
        logger.info(f"Fehlgeschlagene Versuche: {self.failed_attempts}")
        if self.total_attempts > 0:
            success_rate = (self.successful_attempts / self.total_attempts) * 100
            logger.info(f"Erfolgsrate: {success_rate:.1f}%")

def main():
    """Hauptfunktion"""
    chromedriver_path = "/usr/bin/chromedriver"

    # Prüfen ob ChromeDriver existiert
    if not os.path.exists(chromedriver_path):
        print("FEHLER: ChromeDriver nicht gefunden.")
        print("Installation für Linux:")
        print("1. sudo apt-get update")
        print("2. sudo apt-get install -y chromium-driver")
        print("3. Oder manuell von https://chromedriver.chromium.org/downloads")
        print(f"4. ChromeDriver nach {chromedriver_path} kopieren")
        sys.exit(1)

    # Prüfen ob Chromium existiert
    chrome_paths = ["/usr/bin/chromium"]
    chrome_exists = any(os.path.exists(path) for path in chrome_paths)
    if not chrome_exists:
        print("FEHLER: Chromium nicht gefunden.")
        print("Installation:")
        print("1. sudo apt-get update")
        print("2. sudo apt-get install -y chromium")
        sys.exit(1)

    tester = ChromeBotTester(chromedriver_path)

    try:
        max_input = ""  # Standard: unbegrenzt
        if max_input == "":
            max_attempts = None
        elif max_input.lower() in ['unbegrenzt', 'unlimited', 'infinite', '0']:
            max_attempts = None
        else:
            try:
                max_attempts = int(max_input)
                if max_attempts <= 0:
                    max_attempts = None
            except ValueError:
                max_attempts = 50  # Fallback

        delay = 10  # Standardpause
        tester.run_test_loop(max_attempts, delay)

    except ValueError:
        print("Ungültige Eingabe. Verwende Standardwerte.")
        tester.run_test_loop(50, 10)

if __name__ == "__main__":
    print("=== CHROMIUM BOT TESTER ===")
    print("Für autorisierte Cybersicherheitstests")
    print("Drücke Ctrl+C zum Beenden")
    print("Gib 'unbegrenzt' oder leer ein für unbegrenzte Versuche\n")
    main()