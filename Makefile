ROOT ?= data/raw/CottonWeedDet12/CottonWeedDet12

.PHONY: data
data:
	python -m weedlab.prepare --root $(ROOT)