#VERSION: 1.00
# AUTHORS: Daniel Naranjo (garcianaranjodaniel@gmail.com)
# LICENSING INFORMATION

from helpers import download_file, retrieve_url
from novaprinter import prettyPrinter
import re

class dontorrent(object):
    url = 'https://dontorrent.prof'
    name = 'DonTorrent'
    supported_categories = {
        'all': '',
    }

    def __init__(self):
        """
        Some initialization
        """

    def download_torrent(self, url):
        print(download_file(url))
        

    # DO NOT CHANGE the name and parameters of this function
    # This function will be the one called by nova2.py
    def search(self, what, cat='all'):
        search_url = f"{self.url}/buscar/{what.replace('+','%20')}"
        html = retrieve_url(search_url)
        """
        Para saber si ha encontrado torrents, en dontorrent te muestra un mensaje con la cantidad de torrents encontrados
        Si no encuentra nada, la cantidad de torrents es 0
        """
        quantity = re.findall(r'<p.*?class="lead.*?</p>', html)
        try:
            quantity = re.findall('<b>(.*?)</b>', quantity[1])[0]
            quantity = int(quantity)
        except IndexError:
            """
            Por algún motivo, aveces al señor dontorrent le da por directamente no mostrar nada
            Da igual si esa búsqueda tiene resultados o no, no muestra nada
            """
            quantity = 0

        """
        En la paginación tiene dos botones que son para ir a la pagina anterior y a la siguiente
        Por ello uso pages[1:-1] para quitar esos dos botones
        """
        if quantity > 0:
            pages = re.findall(r'<a.*?class="page-link.*?</a>', html)
            pages = pages[1:-1]
            pages = len(pages)
        else:
            pages = 0

        
        links = []

        """
        Las páginas tienen la siguiente estructura: url/buscar/what/page/[0-pages]
        Por ejemplo: https://dontorrent.cologne/buscar/star%20wars/page/1
        """
        for i in range(2, pages + 1):
            url = f"{self.url}/buscar/{what.replace('+','%20')}/page/{i}"
            html = retrieve_url(url)

            a_list = re.findall(r'<a.*?class="text-decoration-none.*?</a>', html)
            for a in a_list:
                url = re.findall(r'href=[\'"]?([^\'" >]+)', a)
                if len(url) > 0:
                    links.append(url[0])
            
        """
        Porque no accedo a la pagina 1?
        Básicamente al señor dontorrent aveces le da por no mostrar los resultados de las paginas que tienen la siguiente estructura:
        https://dontorrent.cologne/buscar/star%20wars/page/1
        Puede ser la página 1 como la 5. Así que para asegurarme obtener resultados, visito la página https://dontorrent.cologne/buscar/star%20wars
        que es equivalente a https://dontorrent.cologne/buscar/star%20wars/page/1

        Aun así puede no dar resultados pero si los da, me aseguro de que almenos devuelva algunos resultados
        """
        url = f"{self.url}/buscar/{what.replace('+','%20')}"
        html = retrieve_url(url)
        a_list = re.findall(r'<a.*?class="text-decoration-none.*?</a>', html)
        for a in a_list:
            url = re.findall(r'href=[\'"]?([^\'" >]+)', a)
            if len(url) > 0:
                links.append(url[0])

        for i in links:
            url = f"{self.url}{i}"
            html = retrieve_url(url)
            item = {}
            item['seeds'] = '-1'
            item['leech'] = '-1'
            item['engine_url'] = self.url
            item['desc_link'] = i
            item['name'] = name = i.split("/")[-1].replace("-", " ")

            if i.split("/")[1] != "serie":
                tam = re.findall(r'<p.*?class="mb-0.*?</p>', html)

                if len(tam) > 0:
                    if len(tam) == 2:
                        tam = tam[1]
                    else:
                        tam = tam[0]
                    
                    content = tam[tam.rfind("b")+2 : tam.rfind("<")]
                    content=content.strip()
                else:
                    content = "-1"

                content = content.replace(",", ".")
                item['size'] = content
                
                download_link = re.findall(r'<a.*?class="text-white bg-primary rounded-pill d-block shadow text-decoration-none p-1.*?</a>', html)

                if len(download_link) == 0:
                    # Esto ocurre si se accede a un enlace que es un documental
                    download_link = re.findall(r'<a.*?class="text-white bg-primary rounded-pill d-block shadow-sm text-decoration-none my-1 py-1.*?</a>', html)

                download_link = "https:" + re.findall(r'href=[\'"]?([^\'" >]+)', download_link[0])[0]
                item['link'] = download_link
                prettyPrinter(item)
            else:
                tds = re.findall(r'<tr>(.*?)</tr>', html, re.M|re.I|re.S)
                tds = tds[1:]
                for td in tds:
                    td_content = re.findall(r'<td.*?>(.*?)</td>', td, re.DOTALL)
                    a = td_content[1]

                    try:
                        download_link = "https:" + re.findall(r'href=[\'"]?([^\'" >]+)', a)[0]
                        item['link'] = download_link
                        item['size'] = -1
                        item['name'] = name + " " + td_content[0]
                        prettyPrinter(item)
                    except Exception:
                        continue


