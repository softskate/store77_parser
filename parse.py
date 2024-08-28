import time
from bs4 import BeautifulSoup
import requests
from database import Product, ProductDetails


class Parser:
    @staticmethod
    def get_jhash(b):
        x = 123456789
        k = 0
        for i in range(1677696):
            x = ((x + b) ^ (x + (x % 3) + (x % 17) + b) ^ i) % 16776960
            if x % 117 == 0:
                k = (k + 1) % 1111
        return k
    
    def __init__(self) -> None:
        self.sess = requests.Session()
        headers = {
            'accept': '*/*',
            'accept-encoding': 'gzip, deflate, br, zstd',
            'accept-language': 'en-US,en;q=0.9,ru-RU;q=0.8,ru;q=0.7',
            'connection': 'keep-alive',
            'dnt': '1',
            'host': 'store77.net',
            'sec-ch-ua': '"Not)A;Brand";v="99", "Google Chrome";v="127", "Chromium";v="127"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36'
        }
        self.sess.headers.update(headers)
        while True:
            resp = self.sess.get('https://store77.net/')
            if resp.history:
                self.bxajaxid = resp.text.split("'bxajaxid', '", 1)[1].split("'", 1)[0]
                break
            
            if not '__js_p_' in resp.cookies: break
            code, age, sec, disable_utm = resp.cookies['__js_p_'].split(',')[:4]
            jhash = self.get_jhash(int(code))
            cookies = {
                '__jhash_': str(jhash),
                'max-age': age,
                'Path': '/',
                '__jua_': 'Mozilla%2F5.0%20%28Windows%20NT%2010.0%3B%20Win64%3B%20x64%29%20AppleWebKit%2F537.36%20%28KHTML%2C%20like%20Gecko%29%20Chrome%2F126.0.0.0%20Safari%2F537.36',
            }
            if sec:
                cookies['SameSite'] = 'None;Secure'

            for key, value in cookies.items():
                self.sess.cookies.set_cookie(requests.cookies.create_cookie(key, value, domain='store77.net'))

        self.last_init = time.time()

    def parse_product_list(self, url, appid, crawlid):
        resp = self.sess.get(url)
        resp = resp.text

        for js_data in resp.split('<script>'):
            js_data = js_data.strip()
            if js_data.startswith('dataLayer'):
                break
        
        imp = {}
        page = js_data.split('s7CatalogList({')[1].split('});')[0].strip()
        for row in page.splitlines():
            key, value = [x.strip("', ") for x in row.split(':', 1)]
            imp[key] = value

        imp['PageSize'] = int(imp['PageSize'])
        imp['SelectedCount'] = int(imp['SelectedCount'])

        params = {
            'pagesize': imp['PageSize'],
            'bxajaxid': imp['bxajaxid'],
            'AJAX_GET_NEXT_PAGE': 'Y',
            'PAGEN_1': 0
        }

        page_cnt = -(-imp['SelectedCount'] // imp['PageSize'])
        for page_num in range(1, page_cnt+1):
            params['PAGEN_1'] = page_num

            resp = self.sess.get(url, params=params, headers={'bx-ajax': 'true'})
            js_data = resp.json()
            if not js_data['IsSuccess']:
                break
            soup = BeautifulSoup(js_data['html'], 'html.parser')
            prods = soup.find_all('div', {'class': 'blocks_product_fix_w'})
            for prod in prods:
                det_url = 'https://store77.net' + prod.a.attrs['href']
                image = prod.find('div', {'class': 'bp_product_img'}).img.attrs['src']
                js_data = prod.a.attrs['onclick'].split("'products': [{")[1].split("'list'")[0]
                prod = {}
                for pm in js_data.strip().splitlines():
                    key, val = pm.split(':', 1)
                    key = key.strip("' ")
                    val = val.split('//')[0].strip("', ")
                    prod[key] = val

                prod['category'] = prod['category'].replace('/', ' - ')
                prod['productId'] = prod.pop('id')
                prod['productUrl'] = det_url
                prod['imageUrl'] = image
                prod['appid'] = appid
                prod['crawlid'] = crawlid
                Product.create(**prod)
                exist = ProductDetails.get_or_none(productId = prod['productId'])
                if not exist:
                    self.parse_details(det_url, prod['productId'], appid, crawlid)


    def parse_details(self, url, productId, appid, crawlid):
        resp = self.sess.get(url)
        soup = BeautifulSoup(resp.content, 'html.parser')

        desc = soup.select_one('div.wrap_descr_b')
        desc = desc.get_text('\n', True)
        images = ['https://store77.net'+x.attrs['src'] for x in soup.select('div.slick-offer-img-big img')]

        details = {}
        params = soup.select_one('div.pages_card__sidebar div.card_product_payment')
        for param in params.select('p.cpp_block_p'):
            key, val = param.get_text(strip=True).split(':', 1)
            key = key.strip()
            val = val.replace('\r\n', '')
            while '  ' in val:
                val = val.replace('  ', ' ')
            details[key] = val

        dets = soup.select_one('#cardOptions ul.swiper-wrapper')
        for row in dets.select('li.swiper-slide'):
            tab_id = row.a.attrs['href']
            tab_name = row.a.get_text(strip=True)
            tab = soup.select_one(tab_id)
            for trow in tab.select('tr'):
                trow = trow.select('td')
                if not trow: continue
                key, val = [x.get_text(strip=True) for x in trow]
                if tab_name in details:
                    details[tab_name] += f'\n{key}: {val}'
                else:
                    details[tab_name] = f'{key}: {val}'


        ProductDetails.create(
            appid = appid,
            crawlid = crawlid,
            productId = productId,
            description = desc,
            imageUrls = images,
            details = details,
        )

