/**
 * Static Bun dependencies for the standalone Python plugins.
 *
 * Bun's test watcher follows imported files. Importing each plugin as text
 * keeps the engines standalone while making bun test --watch rerun the
 * repository tests when an engine changes.
 */
import academictorrentsSource from "../plugins/academictorrents.py" with { type: "text" };
import acgripSource from "../plugins/acgrip.py" with { type: "text" };
import ali213Source from "../plugins/ali213.py" with { type: "text" };
import anidexSource from "../plugins/anidex.py" with { type: "text" };
import animetoshoSource from "../plugins/animetosho.py" with { type: "text" };
import apachetorrentSource from "../plugins/apachetorrent.py" with { type: "text" };
import audiobookbaySource from "../plugins/audiobookbay.py" with { type: "text" };
import bitsearchSource from "../plugins/bitsearch.py" with { type: "text" };
import bt4gprxSource from "../plugins/bt4gprx.py" with { type: "text" };
import btdigSource from "../plugins/btdig.py" with { type: "text" };
import calidadtorrentSource from "../plugins/calidadtorrent.py" with { type: "text" };
import cloudtorrentsSource from "../plugins/cloudtorrents.py" with { type: "text" };
import cpasbienSource from "../plugins/cpasbien.py" with { type: "text" };
import darklibriaSource from "../plugins/darklibria.py" with { type: "text" };
import divxtotalSource from "../plugins/divxtotal.py" with { type: "text" };
import dmhySource from "../plugins/dmhy.py" with { type: "text" };
import dodi_repacksSource from "../plugins/dodi_repacks.py" with { type: "text" };
import dontorrentSource from "../plugins/dontorrent.py" with { type: "text" };
import elitetorrentSource from "../plugins/elitetorrent.py" with { type: "text" };
import esmeraldatorrentSource from "../plugins/esmeraldatorrent.py" with { type: "text" };
import eztvxSource from "../plugins/eztvx.py" with { type: "text" };
import fitgirl_repacksSource from "../plugins/fitgirl_repacks.py" with { type: "text" };
import glotorrentsSource from "../plugins/glotorrents.py" with { type: "text" };
import goggamesSource from "../plugins/goggames.py" with { type: "text" };
import kickasstorrentsSource from "../plugins/kickasstorrents.py" with { type: "text" };
import magnetdlSource from "../plugins/magnetdl.py" with { type: "text" };
import maxitorrentSource from "../plugins/maxitorrent.py" with { type: "text" };
import mejortorrentSource from "../plugins/mejortorrent.py" with { type: "text" };
import mikanSource from "../plugins/mikan.py" with { type: "text" };
import mikananiSource from "../plugins/mikanani.py" with { type: "text" };
import mypornclubSource from "../plugins/mypornclub.py" with { type: "text" };
import naranjatorrentSource from "../plugins/naranjatorrent.py" with { type: "text" };
import nekobtSource from "../plugins/nekobt.py" with { type: "text" };
import nyaa_phuongSource from "../plugins/nyaa_phuong.py" with { type: "text" };
import nyaapantsuSource from "../plugins/nyaapantsu.py" with { type: "text" };
import nyaasiSource from "../plugins/nyaasi.py" with { type: "text" };
import onlinefixSource from "../plugins/onlinefix.py" with { type: "text" };
import pirateiroSource from "../plugins/pirateiro.py" with { type: "text" };
import redetorrentSource from "../plugins/redetorrent.py" with { type: "text" };
import rockboxSource from "../plugins/rockbox.py" with { type: "text" };
import rutorSource from "../plugins/rutor.py" with { type: "text" };
import sktorrentSource from "../plugins/sktorrent.py" with { type: "text" };
import smallgamesSource from "../plugins/smallgames.py" with { type: "text" };
import snowflSource from "../plugins/snowfl.py" with { type: "text" };
import solidtorrentsSource from "../plugins/solidtorrents.py" with { type: "text" };
import subspleaseSource from "../plugins/subsplease.py" with { type: "text" };
import sukebeisiSource from "../plugins/sukebeisi.py" with { type: "text" };
import thepiratebaySource from "../plugins/thepiratebay.py" with { type: "text" };
import therarbgSource from "../plugins/therarbg.py" with { type: "text" };
import tokyotoshokanSource from "../plugins/tokyotoshokan.py" with { type: "text" };
import tomadivxSource from "../plugins/tomadivx.py" with { type: "text" };
import torrent9Source from "../plugins/torrent9.py" with { type: "text" };
import torrentdownloadSource from "../plugins/torrentdownload.py" with { type: "text" };
import torrentdownloadsSource from "../plugins/torrentdownloads.py" with { type: "text" };
import torrentgalaxySource from "../plugins/torrentgalaxy.py" with { type: "text" };
import trahtSource from "../plugins/traht.py" with { type: "text" };
import uniondhtSource from "../plugins/uniondht.py" with { type: "text" };
import xxxclubtoSource from "../plugins/xxxclubto.py" with { type: "text" };
import yggtrackerSource from "../plugins/yggtracker.py" with { type: "text" };
import yourbittorrentSource from "../plugins/yourbittorrent.py" with { type: "text" };
import ytsSource from "../plugins/yts.py" with { type: "text" };

export const PLUGIN_SOURCES = {
  academictorrents: academictorrentsSource,
  acgrip: acgripSource,
  ali213: ali213Source,
  anidex: anidexSource,
  animetosho: animetoshoSource,
  apachetorrent: apachetorrentSource,
  audiobookbay: audiobookbaySource,
  bitsearch: bitsearchSource,
  bt4gprx: bt4gprxSource,
  btdig: btdigSource,
  calidadtorrent: calidadtorrentSource,
  cloudtorrents: cloudtorrentsSource,
  cpasbien: cpasbienSource,
  darklibria: darklibriaSource,
  divxtotal: divxtotalSource,
  dmhy: dmhySource,
  dodi_repacks: dodi_repacksSource,
  dontorrent: dontorrentSource,
  elitetorrent: elitetorrentSource,
  esmeraldatorrent: esmeraldatorrentSource,
  eztvx: eztvxSource,
  fitgirl_repacks: fitgirl_repacksSource,
  glotorrents: glotorrentsSource,
  goggames: goggamesSource,
  kickasstorrents: kickasstorrentsSource,
  magnetdl: magnetdlSource,
  maxitorrent: maxitorrentSource,
  mejortorrent: mejortorrentSource,
  mikan: mikanSource,
  mikanani: mikananiSource,
  mypornclub: mypornclubSource,
  naranjatorrent: naranjatorrentSource,
  nekobt: nekobtSource,
  nyaa_phuong: nyaa_phuongSource,
  nyaapantsu: nyaapantsuSource,
  nyaasi: nyaasiSource,
  onlinefix: onlinefixSource,
  pirateiro: pirateiroSource,
  redetorrent: redetorrentSource,
  rockbox: rockboxSource,
  rutor: rutorSource,
  sktorrent: sktorrentSource,
  smallgames: smallgamesSource,
  snowfl: snowflSource,
  solidtorrents: solidtorrentsSource,
  subsplease: subspleaseSource,
  sukebeisi: sukebeisiSource,
  thepiratebay: thepiratebaySource,
  therarbg: therarbgSource,
  tokyotoshokan: tokyotoshokanSource,
  tomadivx: tomadivxSource,
  torrent9: torrent9Source,
  torrentdownload: torrentdownloadSource,
  torrentdownloads: torrentdownloadsSource,
  torrentgalaxy: torrentgalaxySource,
  traht: trahtSource,
  uniondht: uniondhtSource,
  xxxclubto: xxxclubtoSource,
  yggtracker: yggtrackerSource,
  yourbittorrent: yourbittorrentSource,
  yts: ytsSource,
} as const;
