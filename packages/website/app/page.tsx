import { DOWNLOAD_URL, RELEASES_URL, REPOSITORY_URL } from "../lib/links";

export const dynamic = "force-static";

export default function HomePage() {
  return (
    <div className="site-shell">
      <main>
        <header className="download">
          <h1>qbsearch</h1>
          <p className="description">Search plugins for qBittorrent.</p>
          <a className="download-button" href={DOWNLOAD_URL}>
            Download ZIP
          </a>
          <p className="archive-details">
            Includes plugins, icons, and installers for Windows, macOS, and Linux.
          </p>
          <a className="releases-link" href={RELEASES_URL}>
            All releases
          </a>
        </header>

        <section className="installation" aria-labelledby="install-heading">
          <h2 id="install-heading">Install</h2>
          <p>You need qBittorrent and Python 3.9+.</p>
          <ol className="install-steps">
            <li>Download and extract the ZIP.</li>
            <li>
              Quit qBittorrent. Open a terminal in the extracted folder and run the command for your
              system. On Windows, use PowerShell.
              <dl className="commands">
                <div>
                  <dt>macOS</dt>
                  <dd>
                    <code>sh install/macos.sh</code>
                  </dd>
                </div>
                <div>
                  <dt>Linux</dt>
                  <dd>
                    <code>sh install/linux.sh</code>
                  </dd>
                </div>
                <div>
                  <dt>Windows</dt>
                  <dd>
                    <code>{".\\install\\windows.ps1"}</code>
                  </dd>
                </div>
              </dl>
            </li>
            <li>
              Reopen qBittorrent. If the Search tab is hidden, enable{" "}
              <strong>View → Search Engine</strong>.
            </li>
          </ol>
          <p className="collection-note">The full collection includes adult search plugins.</p>
        </section>
      </main>

      <footer>
        <nav aria-label="More information">
          <a href={`${REPOSITORY_URL}/blob/main/documentation/INSTALL.md`}>Installation guide</a>
          <a href={`${REPOSITORY_URL}/blob/main/documentation/PLUGINS.md`}>Plugin list</a>
          <a href={REPOSITORY_URL}>GitHub</a>
          <a href={`${REPOSITORY_URL}/blob/main/LICENSE.md`}>License</a>
        </nav>
      </footer>
    </div>
  );
}
