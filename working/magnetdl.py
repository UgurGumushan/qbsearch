# VERSION: 1.4
"""
MagnetDL magnet link search. Follows result pages 1 to 30, stopping early if
the footer's total result count is reached before the 30-page cap.
"""

# magnetdl.com
# first thirty pages
import re

from helpers import retrieve_url

# qBt
from novaprinter import SearchResults, prettyPrinter


# noinspection PyPep8Naming
class magnetdl:
    url = "http://www.magnetdl.com/"
    name = "MagnetDL"
    result_page_match = re.compile(
        r'<td\sclass="m"><a\shref="(magnet.*?)"\stitle=".*?class="n"><a\shref="(.*?)"\stitle="(.*?)">.*?<td\sclass="t.">.*?</td><td>.*?</td><td>(.*?)</td><td\sclass="s">(.*?)</td><td\sclass="l">(.*?)</td>'
    )
    total_results_num = re.compile(
        r'<div id="footer">Found <strong>(.*)<\/strong> Magnet Links for <i>'
    )

    def search(self, what: str, cat: str = "all") -> None:
        what = what.lower()
        running_total, total_results, pages = 0, 1, 0

        while running_total < total_results and pages <= 29:
            pages += 1
            query = self.url + what[:1] + "/" + what.replace("%20", "-") + "/" + str(pages)
            # print(query)
            data = retrieve_url(query)
            total_results = int(re.findall(self.total_results_num, data)[0].replace(",", ""))
            results = re.findall(self.result_page_match, data)

            for result in results:
                temp_result = SearchResults(
                    name=result[2].replace("|", ""),
                    size=result[3].replace(",", ""),
                    link=result[0],
                    desc_link=self.url[:-1] + result[1],
                    seeds=int(result[4]),
                    leech=int(result[5]),
                    engine_url=self.url,
                )
                prettyPrinter(temp_result)
                running_total += 1


if __name__ == "__main__":
    engine = magnetdl()
    engine.search("Ebook")
