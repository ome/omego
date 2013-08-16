release:
	git describe --exact
	python setup.py sdist upload --sign

clean:
	rm -rf build dist omego.egg-info *.pyc

.PHONY: register clean
