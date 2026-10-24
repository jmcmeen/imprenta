# API

`imprenta.Project` is the public surface; the command line and the manager are
thin layers over it. Catalogs and targets are what it hands back.

```python
from imprenta import Project

project = Project.find()               # the repo that holds catalog.*.yaml
for target in project.targets():       # (catalog, product, variant)
    project.build(target)
errors, warnings = project.check()
```

::: imprenta.Project

::: imprenta.Catalog

::: imprenta.Target
