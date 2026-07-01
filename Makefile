.PHONY: html serve clean
html:
	sphinx-build -b html docs _build/html
serve: html
	python -m http.server -d _build/html 8000
clean:
	rm -rf _build docs/_build
