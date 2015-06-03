
from django.db import models

from nodeconductor.structure import models as structure_models
from nodeconductor.iaas import models as iaas_models


class OracleService(structure_models.Service):
    projects = models.ManyToManyField(
        structure_models.Project, related_name='oracle_services', through='OracleServiceProjectLink')


class OracleServiceProjectLink(structure_models.ServiceProjectLink):
    service = models.ForeignKey(OracleService)


class Zone(structure_models.ServiceProperty):
    pass


class Template(structure_models.ServiceProperty):

    class Types:
        DB = 1
        SCHEMA = 2

        CHOICES = (
            (DB, 'Database Platform Template'),
            (SCHEMA, 'Schema Platform Template'),
        )

    type = models.SmallIntegerField(choices=Types.CHOICES)


class Database(structure_models.Resource, iaas_models.ServiceMixin):
    service_project_link = models.ForeignKey(
        OracleServiceProjectLink, related_name='databases', on_delete=models.PROTECT)
