import {
  ArrowDownIcon,
  ArrowUpRightIcon,
  CheckIcon,
  CodeIcon,
  DownloadIcon,
  GridIcon,
  ShieldIcon,
  SparkIcon,
  TerminalIcon,
} from "@/components/icons";
import { PluginDirectory } from "@/components/plugin-directory";
import { categoryLabel, getCatalog, RELEASES_URL, REPOSITORY_URL } from "@/lib/catalog";

export const dynamic = "force-static";

export default async function HomePage() {
  const plugins = await getCatalog();
  const activeCount = plugins.filter((plugin) => plugin.status === "active").length;
  const categoryCount = new Set(plugins.map((plugin) => plugin.category)).size;
  const categorySummary = Array.from(new Set(plugins.map((plugin) => plugin.category)))
    .sort()
    .slice(0, 4)
    .map(categoryLabel)
    .join(" · ");

  return (
    <main>
      <nav className="site-nav" aria-label="Main navigation">
        <a className="brand" href="#top" aria-label="qbsearch home">
          <span className="brand-mark" aria-hidden="true">
            <span />
            <span />
            <span />
          </span>
          <span className="brand-wordmark">qbsearch</span>
        </a>
        <div className="nav-links">
          <a href="#directory">Directory</a>
          <a href="#install">Install</a>
          <a href={REPOSITORY_URL} target="_blank" rel="noreferrer">
            GitHub <ArrowUpRightIcon width={14} height={14} />
          </a>
        </div>
        <a className="nav-download" href="/download/latest">
          Get the pack <DownloadIcon width={15} height={15} />
        </a>
      </nav>

      <section className="hero section-frame" id="top">
        <div className="hero-copy">
          <p className="eyebrow">
            <span className="eyebrow-pulse" /> qBittorrent / nova3 collection
          </p>
          <h1>
            Make search feel <em>built in.</em>
          </h1>
          <p className="hero-lede">
            A curated set of standalone search engines for qBittorrent. Find the right plugin,
            download one release package, and get back to searching.
          </p>
          <div className="hero-actions">
            <a className="button button-primary" href="/download/latest">
              <DownloadIcon width={18} height={18} />
              Download latest pack
              <span className="button-arrow">↗</span>
            </a>
            <a className="text-link" href="#directory">
              Explore the directory <ArrowDownIcon width={16} height={16} />
            </a>
          </div>
          <div className="hero-proof">
            <div className="proof-avatars" aria-hidden="true">
              <span>YT</span>
              <span>NY</span>
              <span>AT</span>
              <span>+</span>
            </div>
            <p>
              <strong>{activeCount} active engines</strong>
              <span>kept in one release</span>
            </p>
          </div>
        </div>

        <div className="hero-visual" aria-label="Release package preview">
          <div className="visual-grid" />
          <div className="visual-orbit orbit-one" />
          <div className="visual-orbit orbit-two" />
          <div className="visual-core">
            <span className="core-symbol">qb</span>
            <span className="core-label">search</span>
          </div>
          <div className="float-card float-card-top">
            <span className="float-icon float-icon-lime">
              <GridIcon width={16} height={16} />
            </span>
            <span>
              <strong>{plugins.length} plugins</strong>
              <small>{categoryCount} categories</small>
            </span>
          </div>
          <div className="float-card float-card-bottom">
            <span className="float-icon float-icon-cream">
              <ShieldIcon width={16} height={16} />
            </span>
            <span>
              <strong>One clean archive</strong>
              <small>Install scripts included</small>
            </span>
            <CheckIcon className="float-check" width={16} height={16} />
          </div>
          <div className="visual-caption">release package / ready to install</div>
        </div>
      </section>

      <section className="stat-strip section-frame" aria-label="Collection highlights">
        <div className="stat-item">
          <span className="stat-value">{plugins.length}</span>
          <span className="stat-label">standalone engines</span>
        </div>
        <div className="stat-item">
          <span className="stat-value">{categoryCount}</span>
          <span className="stat-label">search categories</span>
        </div>
        <div className="stat-item">
          <span className="stat-value">3.9+</span>
          <span className="stat-label">Python compatibility</span>
        </div>
        <div className="stat-item stat-note">
          <span className="stat-signal" />
          <span className="stat-label">{categorySummary} & more</span>
        </div>
      </section>

      <section className="feature-section section-frame">
        <div className="section-kicker">Why qbsearch</div>
        <div className="feature-heading">
          <h2>Less hunting. More finding.</h2>
          <p>
            Every engine is its own installable file, while the collection release keeps the whole
            setup simple.
          </p>
        </div>
        <div className="feature-grid">
          <article className="feature-card feature-card-dark">
            <div className="feature-icon">
              <SparkIcon width={20} height={20} />
            </div>
            <p className="feature-number">01 / focused</p>
            <h3>Search where you already are</h3>
            <p>Bring more sources into qBittorrent&apos;s native Search tab without a new app.</p>
          </article>
          <article className="feature-card">
            <div className="feature-icon feature-icon-lime">
              <CodeIcon width={20} height={20} />
            </div>
            <p className="feature-number">02 / standalone</p>
            <h3>Portable by design</h3>
            <p>
              Each plugin remains a self-contained nova3 engine with no shared runtime to install.
            </p>
          </article>
          <article className="feature-card">
            <div className="feature-icon feature-icon-orange">
              <TerminalIcon width={20} height={20} />
            </div>
            <p className="feature-number">03 / ready</p>
            <h3>One package, three installers</h3>
            <p>Download the CI-built ZIP and use the native script for macOS, Linux, or Windows.</p>
          </article>
        </div>
      </section>

      <section className="install-section section-frame" id="install">
        <div className="install-intro">
          <div className="section-kicker">From download to discovery</div>
          <h2>A tidy handoff to your Search tab.</h2>
          <p>
            The release archive contains the engines, matching icons, support files, and native
            installers. No Python, Bun, or repository checkout is needed on the target machine.
          </p>
          <a className="button button-dark" href="/download/latest">
            <DownloadIcon width={17} height={17} />
            Download the collection
          </a>
          <a
            className="under-link"
            href={`${REPOSITORY_URL}/blob/main/documentation/INSTALL.md`}
            target="_blank"
            rel="noreferrer"
          >
            Read full install notes <ArrowUpRightIcon width={14} height={14} />
          </a>
        </div>
        <div className="install-steps">
          <div className="install-step">
            <span className="step-index">01</span>
            <div>
              <h3>Download the release ZIP</h3>
              <p>It is built by CI and includes the complete plugin collection.</p>
            </div>
            <ArrowDownIcon width={17} height={17} />
          </div>
          <div className="install-step">
            <span className="step-index">02</span>
            <div>
              <h3>Run your platform installer</h3>
              <p>
                Use <code>install/macos.sh</code>, <code>install/linux.sh</code>, or PowerShell.
              </p>
            </div>
            <TerminalIcon width={17} height={17} />
          </div>
          <div className="install-step">
            <span className="step-index">03</span>
            <div>
              <h3>Open qBittorrent and search</h3>
              <p>Quit qBittorrent during install, then relaunch and open the Search tab.</p>
            </div>
            <CheckIcon width={17} height={17} />
          </div>
        </div>
      </section>

      <section className="directory-section section-frame" id="directory">
        <div className="directory-heading">
          <div>
            <div className="section-kicker">The directory</div>
            <h2>Find your next source.</h2>
          </div>
          <p>
            Browse the catalog by category or search by name. Status describes repository support,
            not a guarantee that a remote site is online right now.
          </p>
        </div>
        <PluginDirectory plugins={plugins} />
      </section>

      <section className="closing-cta section-frame">
        <div>
          <p className="eyebrow eyebrow-dark">
            <span className="eyebrow-pulse" /> ready when you are
          </p>
          <h2>Turn on a bigger search.</h2>
        </div>
        <div className="closing-actions">
          <a className="button button-primary" href="/download/latest">
            <DownloadIcon width={18} height={18} />
            Download latest pack
          </a>
          <a
            className="text-link text-link-dark"
            href={RELEASES_URL}
            target="_blank"
            rel="noreferrer"
          >
            All releases <ArrowUpRightIcon width={16} height={16} />
          </a>
        </div>
      </section>

      <footer className="site-footer section-frame">
        <a className="brand" href="#top">
          <span className="brand-mark" aria-hidden="true">
            <span />
            <span />
            <span />
          </span>
          <span className="brand-wordmark">qbsearch</span>
        </a>
        <p>Standalone nova3 search engines for qBittorrent.</p>
        <div className="footer-links">
          <a href={`${REPOSITORY_URL}/blob/main/LICENSE.md`} target="_blank" rel="noreferrer">
            License
          </a>
          <a href={REPOSITORY_URL} target="_blank" rel="noreferrer">
            GitHub <ArrowUpRightIcon width={13} height={13} />
          </a>
        </div>
      </footer>
    </main>
  );
}
