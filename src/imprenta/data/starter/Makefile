# The catalog decides what gets built; the target name says which one right now.
#
#   make                        check, then build everything every catalog subscribes
#   make main                   one catalog (catalog.main.yaml): all its products
#   make lorem                  one product, in every catalog that has it
#   make main/lorem             one catalog's product
#   make lorem.ebook            one variant, subscribed or not (also main/lorem.ebook)
#   make preview-main/lorem     live Paged.js preview in the browser (HTML in tmp/)
#   make manager                the TUI
#   make check                  validate content and catalogs
#   make status                 every product of every catalog
#   make doctor                 pandoc / node / pagedjs-cli / Chrome / fonts
#   make clean                  wipe output/ and tmp/
#   make setup                  install deps (uv sync + npm ci), fetch fonts, check tools
#
# Add FORCE=1 to any build to rebuild even when the output is up to date.

.PHONY: all check status doctor manager clean setup help
.DEFAULT_GOAL := all

UV := uv run
FORCEFLAG := $(if $(FORCE),--force,)

all: check
	$(UV) imprenta build $(FORCEFLAG)

check:
	@$(UV) imprenta check

status:
	@$(UV) imprenta status

doctor:
	@$(UV) imprenta doctor

manager:
	@$(UV) imprenta manager

clean:
	rm -rf output tmp

# PUPPETEER_SKIP_DOWNLOAD: pagedjs-cli depends on puppeteer, which would download
# its own ~150 MB Chromium. The build drives the system Chrome instead.
setup:
	uv sync
	PUPPETEER_SKIP_DOWNLOAD=1 npm ci --no-fund --no-audit
	$(UV) python scripts/fetch_fonts.py templates/fonts
	@$(UV) imprenta doctor

help:
	@sed -n '2,16p' Makefile | cut -c3-

preview-%:
	$(UV) imprenta build --preview $*

# Anything else is a catalog, a product, or a product.variant: imprenta parses the name.
%:
	$(UV) imprenta build $@ $(FORCEFLAG)

Makefile: ;
