release:
	git describe --exact
	python setup.py register sdist bdist upload --sign

clean:
	rm -rf build dist omego.egg-info *.pyc

.PHONY: register clean
