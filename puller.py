import imaplib
import email
import re
from email.header import decode_header
import requests
import threading
from queue import Queue
from colorama import init, Fore

# Initialize colorama
init()

# Constants
IMAP_SERVER = 'mail.detroid.shop'
IMAP_PORT = 993
THREAD_COUNT = 10  # Adjust based on your system capabilities

def decode_mime_header(header):
    decoded = decode_header(header)
    return ' '.join([str(t[0], t[1] or 'utf-8') if isinstance(t[0], bytes) else str(t[0]) for t in decoded])

def get_discord_nitro_email_link(email_account: str, email_password: str):
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(email_account, email_password)
        mail.select("inbox")

        status, data = mail.search(None, '(SUBJECT "DISCORD NITRO: GIVEAWAY OFFER")')
        if status != 'OK' or not data[0]:
            mail.logout()
            return None

        email_ids = data[0].split()
        for email_id in reversed(email_ids):  # Process newest first
            status, msg_data = mail.fetch(email_id, '(RFC822)')
            if status != 'OK':
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode(errors="ignore")
                        break
            else:
                if msg.get_content_type() == "text/plain":
                    body = msg.get_payload(decode=True).decode(errors="ignore")

            link_pattern = r'Or, open the following link to view this email in a browser:\s*(https://[^\s]+)'
            match = re.search(link_pattern, body)
            if match:
                mail.logout()
                return match.group(1)

        mail.logout()
        return None

    except Exception as e:
        print(f"{Fore.RED}Error processing {email_account}: {str(e)}{Fore.RESET}")
        return None

def extract_discord_promo_links(view_email_url: str):
    try:
        session = requests.Session()
        response = session.get(view_email_url, timeout=10)

        if response.status_code != 200:
            return []

        promo_links = re.findall(r"https:\/\/promos\.discord\.gg\/[a-zA-Z0-9]+", response.text)
        return promo_links

    except Exception as e:
        return []

def worker(account_queue, results):
    while not account_queue.empty():
        acc = account_queue.get()
        try:
            if ":" not in acc:
                print(f"{Fore.YELLOW}{acc} -> invalid format{Fore.RESET}")
                continue

            email_account, email_password = acc.split(":", 1)
            email_link = get_discord_nitro_email_link(email_account, email_password)
            
            if email_link:
                promo_links = extract_discord_promo_links(email_link)
                if promo_links:
                    result = f"{Fore.WHITE}Pulled Promo {Fore.MAGENTA}> {Fore.WHITE}[{Fore.MAGENTA}{promo_links[0]}{Fore.WHITE}]"
                    with open("promo.txt", "a") as file:
                        for link in promo_links:
                            file.write(link + "\n")

                    with open("combined.txt", "a") as file:
                        for link in promo_links:
                            file.write(f"{acc}:{link}" + "\n")

                    results.append((result, len(promo_links)))
                    print(result)

        except Exception as e:
            print(f"{Fore.RED}Error processing account {acc}: {str(e)}{Fore.RESET}")
        finally:
            account_queue.task_done()

def main():
    # Read accounts from file
    try:
        with open("mails.txt", "r") as f:
            accounts = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"{Fore.RED}Error: mails.txt file not found{Fore.RESET}")
        return

    if not accounts:
        print(f"{Fore.YELLOW}No accounts found in mails.txt{Fore.RESET}")
        return

    # Create queue and add all accounts
    account_queue = Queue()
    for acc in accounts:
        account_queue.put(acc)

    # Store results and count
    results = []
    total_promos = 0

    # Create and start threads
    threads = []
    for _ in range(min(THREAD_COUNT, len(accounts))):
        t = threading.Thread(target=worker, args=(account_queue, results))
        t.start()
        threads.append(t)

    # Wait for all threads to complete
    for t in threads:
        t.join()

    # Calculate total promos
    total_promos = sum(count for (_, count) in results)
    
    # Print summary
    print("\n" + "="*50)
    print(f"{Fore.CYAN}Summary:{Fore.RESET}")
    print(f"{Fore.GREEN}Total promo links found: {total_promos}{Fore.RESET}")
    print(f"{Fore.CYAN}Details:{Fore.RESET}")
    for result, _ in results:
        print(result)

if __name__ == "__main__":
    main()