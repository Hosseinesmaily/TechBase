"""Configure the default Wagtail site.

The Wagtail site (hostname + port) must match how the backend is reached, or
the admin shows every page as "Exploring" (outside any site) and the public
wiki URLs 404.

Run once after `migrate`:
    python manage.py configure_site
"""

from __future__ import annotations

import os

from django.core.management.base import BaseCommand
from wagtail.models import Site


class Command(BaseCommand):
    help = "Point the default Wagtail site at this backend (hostname + port)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--hostname",
            default=os.getenv("WAGTAIL_SITE_HOSTNAME", "localhost"),
            help="Hostname the backend is reached on.",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=int(os.getenv("WAGTAIL_SITE_PORT", "8000")),
            help="Port the backend is reached on.",
        )
        parser.add_argument(
            "--root-path",
            default=None,
            help="Path of the page the site is rooted at (default: the first child of the tree root).",
        )

    def handle(self, *args: object, **options: object) -> None:
        from wagtail.models import Page

        hostname = str(options["hostname"])
        port = int(str(options["port"]))

        site = Site.objects.filter(is_default_site=True).first() or Site.objects.first()
        if site is None:
            self.stderr.write(self.style.ERROR("no Wagtail site exists — run migrate first."))
            return

        root_path = options.get("root_path")
        if root_path:
            root_page = Page.objects.filter(path=root_path).first()
            if root_page is None:
                self.stderr.write(self.style.ERROR(f"no page with path {root_path!r}"))
                return
        else:
            root_page = site.root_page
            # The default Wagtail "home" page is the tree root's first child.
            tree_root = Page.get_first_root_node()
            if tree_root is not None:
                first_child = tree_root.get_children().first()
                if first_child is not None:
                    root_page = first_child

        site.hostname = hostname
        site.port = port
        site.root_page = root_page
        site.is_default_site = True
        site.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"Site: {site.hostname}:{site.port} rooted at "
                f"'{root_page.title}' (path {root_page.path})"
            )
        )
