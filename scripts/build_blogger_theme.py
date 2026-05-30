"""Build blogger-theme.xml from index.html."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "index.html").read_text(encoding="utf-8")

css = re.search(r"<style>(.*?)</style>", src, re.S).group(1).strip()
body = re.search(r"<body>(.*?)<script>", src, re.S).group(1).strip()

css += """

/* ── Blogger overrides ── */
#navbar, #navbar-iframe, .navbar, .blog-feeds, .post-feeds, .feed-links { display: none !important; height: 0; overflow: hidden; visibility: hidden; }
.sidebar { display: none !important; }

/* Hide blog widget output on the landing homepage */
body.homepage #main,
body.homepage .blog-posts,
body.homepage .post-outer,
body.homepage .post,
body.homepage .post-body,
body.homepage #Blog1,
body.homepage .main-inner { display: none !important; visibility: hidden !important; height: 0 !important; max-height: 0 !important; overflow: hidden !important; margin: 0 !important; padding: 0 !important; border: 0 !important; }

/* Always show landing content on Blogger (skip fade-in) */
#md-landing .rv { opacity: 1 !important; transform: none !important; }

/* Force landing cards/grid over Blogger defaults */
#md-landing .feat-grid { display: grid !important; grid-template-columns: 1fr 1fr !important; gap: 12px !important; }
#md-landing .feat { display: block !important; background: #ffffff !important; border: 1px solid #e2e5e9 !important; border-radius: 12px !important; padding: 18px !important; margin: 0 !important; }
#md-landing .checklist { display: block !important; margin: 6px 0 0 !important; padding: 0 !important; list-style: none !important; }
#md-landing .check-item { display: block !important; list-style: none !important; }

.not-home .blog-posts { max-width: 760px; margin: 0 auto; padding: 32px 24px; font-family: 'Inter', system-ui, sans-serif; }
.not-home .post { margin-bottom: 32px; padding-bottom: 24px; border-bottom: 1px solid #e2e5e9; }
.not-home .post-title a { color: #111827; font-size: 1.4rem; font-weight: 700; text-decoration: none; }
.not-home .post-body { color: #374151; line-height: 1.7; margin-top: 12px; }
.not-home .post-footer { font-size: .82rem; color: #9ca3af; margin-top: 12px; }
.not-home-back { display: inline-flex; margin: 16px 24px 0; }

@media (max-width: 860px) {
  #md-landing .feat-grid { grid-template-columns: 1fr !important; }
}
"""


def xml_escape_body(text: str) -> str:
    parts = re.split(r"(&amp;|&lt;|&gt;|&quot;|&#\d+;)", text)
    out = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            out.append(part)
        else:
            out.append(part.replace("&", "&amp;"))
    return "".join(out).replace("&amp;amp;", "&amp;")


def to_xhtml_fragment(html: str) -> str:
    """Self-close void elements required by Blogger XHTML."""
    void_tags = (
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    )
    for tag in void_tags:
        pattern = re.compile(rf"<{tag}\b([^>]*?)>", re.IGNORECASE)

        def repl(match: re.Match, t=tag) -> str:
            attrs = match.group(1).strip()
            if attrs.endswith("/"):
                return match.group(0)
            return f"<{t}{(' ' + attrs) if attrs else ''} />"

        html = pattern.sub(repl, html)
    return html


body = f"<div id='md-landing'>\n{to_xhtml_fragment(xml_escape_body(body))}\n</div>"

script = """(function () {
  var toggle = document.getElementById('toggle');
  var menu = document.getElementById('menu');
  if (toggle && menu) {
    toggle.addEventListener('click', function () { menu.classList.toggle('open'); });
    menu.querySelectorAll('a').forEach(function (a) {
      a.addEventListener('click', function () { menu.classList.remove('open'); });
    });
  }
})();"""

header = """<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns='http://www.w3.org/1999/xhtml' xmlns:b='http://www.google.com/2005/gml/b' xmlns:data='http://www.google.com/2005/gml/data' xmlns:expr='http://www.google.com/2005/gml/expr'>

<head>
  <meta content='width=device-width, initial-scale=1' name='viewport'/>
  <meta content='Media Downloader — free desktop app to download videos, manage downloads, convert media, remove backgrounds with AI, capture your screen, and meet Anika, your optional desktop companion with break reminders and a focus timer.' name='description'/>
  <title><data:blog.pageTitle/></title>
  <link expr:href='data:blog.canonicalHomepageUrl' rel='canonical'/>
  <link href='https://download.ansnew.com/favicon.ico' rel='icon' type='image/x-icon'/>
  <link href='https://fonts.googleapis.com' rel='preconnect'/>
  <link crossorigin='anonymous' href='https://fonts.gstatic.com' rel='preconnect'/>
  <link href='https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&amp;display=swap' rel='stylesheet'/>
  <b:include data='blog' name='all-head-content'/>

  <b:skin><![CDATA[
/*
-----------------------------------------------
Blogger Template: Media Downloader Landing
Developer: ANSNEW TECH — https://inside.ansnew.com
----------------------------------------------- */
"""

footer = f"""{body}
  </b:if>

  <b:if cond='data:blog.url != data:blog.homepageUrl'>
    <a class='btn btn-soft not-home-back' expr:href='data:blog.homepageUrl'>&#8592; Back to Media Downloader</a>
  </b:if>

  <b:section class='main' id='main' maxwidgets='1' showaddelement='no'>
    <b:widget id='Blog1' locked='false' title='Blog Posts' type='Blog'/>
  </b:section>

  <b:section class='sidebar' id='sidebar' maxwidgets='10' showaddelement='yes'>
    <b:widget id='CustomSearch1' locked='false' title='Search' type='CustomSearch'/>
    <b:widget id='FollowByEmail1' locked='false' title='Follow By Email' type='FollowByEmail'/>
    <b:widget id='Label1' locked='false' type='Label'/>
  </b:section>

  <script type='text/javascript'>
  //<![CDATA[
{script}
  //]]>
  </script>

</body>
</html>
"""

middle = """]]></b:skin>
</head>

<body expr:class='data:blog.url == data:blog.homepageUrl ? &quot;md-theme homepage&quot; : &quot;md-theme not-home&quot;'>

  <b:if cond='data:blog.url == data:blog.homepageUrl'>
"""

(ROOT / "blogger-theme.xml").write_text(header + css + middle + footer, encoding="utf-8")
print(f"Wrote {ROOT / 'blogger-theme.xml'}")
