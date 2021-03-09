import logging

from treeherder.model.models import BugzillaComponent, FilesBugzillaMap, Repository
from treeherder.utils.github import fetch_json

logger = logging.getLogger(__name__)


class FilesBugzillaMapProcess:
    bugzilla_components = {}

    max_path_length = FilesBugzillaMap._meta.get_field('path').max_length
    max_product_length = BugzillaComponent._meta.get_field('product').max_length
    max_component_length = BugzillaComponent._meta.get_field('component').max_length

    run_id = None

    def get_or_add_bugzilla_component(self, files_bugzilla_data, path):
        product_component_data = files_bugzilla_data[path]
        product_component_str = product_component_data[0] + " :: " + product_component_data[1]
        if product_component_str in self.bugzilla_components:
            return self.bugzilla_components[product_component_str]
        try:
            product = product_component_data[0]
            component = product_component_data[1]
            if len(product) > self.max_product_length:
                logger.error(
                    "error inserting Bugzilla product and component \"'%s' :: '%s'\" into db (file skipped: '%s'): product is too long (has %d characters, max is %d",
                    product,
                    component,
                    path,
                    len(product),
                    self.max_product_length,
                )
                return
            if len(component) > self.max_component_length:
                logger.error(
                    "error inserting Bugzilla product and component \"'%s' :: '%s'\" into db (file skipped: '%s'): component is too long (has %d characters, max is %d",
                    product,
                    component,
                    path,
                    len(product),
                    self.max_component_length,
                )
                return
            if len(path) > self.max_path_length:
                logger.error(
                    "error inserting Bugzilla product and component \"'%s' :: '%s'\" into db (file skipped: '%s'): path is too long (has %d characters, max is %d",
                    product,
                    component,
                    path,
                    len(path),
                    self.max_path_length,
                )
            bugzilla_component_data, _ = BugzillaComponent.objects.get_or_create(
                product=product,
                component=component,
            )
            self.bugzilla_components[product_component_str] = bugzilla_component_data
        except Exception as e:
            logger.error(
                "error inserting Bugzilla product and component \"'%s' :: '%s'\" into db (file skipped: '%s'): %s",
                product,
                component,
                path,
                e,
            )
            return
        return bugzilla_component_data

    def get_projects_to_import(self):
        return list(
            Repository.objects.filter(codebase='gecko')
            .filter(active_status='active')
            .filter(life_cycle_order__isnull=False)
            .values_list('name', flat=True)
            .order_by('life_cycle_order')
        )

    def fetch_data(self, project):
        url = (
            'https://firefox-ci-tc.services.mozilla.com/api/index/v1/task/gecko.v2.%s.latest.source.source-bugzilla-info/artifacts/public/components.json'
            % project
        )
        files_bugzilla_data = None
        exception = None
        try:
            files_bugzilla_data = fetch_json(url)
        except Exception as e:
            exception = e
        return {
            "url": url,
            "files_bugzilla_data": files_bugzilla_data,
            "exception": exception,
        }

    def run(self):
        projects = self.get_projects_to_import()

        paths_ingested_all = set()
        paths_bugzilla_ingested_all = set()
        for project in projects:
            data_returned = self.fetch_data(project)
            if data_returned["exception"] is not None:
                logger.error(
                    "error fetching file with map of source paths to Bugzilla products and components: url: %s ; %s",
                    data_returned["url"],
                    data_returned["exception"],
                )
                continue
            files_bugzilla_data = data_returned["files_bugzilla_data"]
            paths_ingested_this_project = set(path for path in files_bugzilla_data).difference(
                paths_ingested_all
            )
            paths_bugzilla_ingested_project = set()
            for path in paths_ingested_this_project:
                paths_bugzilla_ingested_project.add(
                    (
                        path,
                        files_bugzilla_data[path][0],
                        files_bugzilla_data[path][1],
                    )
                )

            paths_ingested_all |= paths_ingested_this_project
            paths_bugzilla_ingested_all |= paths_bugzilla_ingested_project

        paths_old = set(FilesBugzillaMap.objects.values_list('path', flat=True))

        paths_removed = paths_old - paths_ingested_all
        FilesBugzillaMap.objects.filter(path__in=paths_removed).delete()

        paths_bugzilla_old = set(
            FilesBugzillaMap.objects.select_related('bugzilla_component').values_list(
                'path', 'bugzilla_component__product', 'bugzilla_component__component'
            )
        )
        paths_bugzilla_unchanged = paths_bugzilla_old.intersection(paths_bugzilla_ingested_all)
        paths_bugzilla_changed_or_added = paths_bugzilla_ingested_all.difference(
            paths_bugzilla_unchanged
        )
        paths_changed_or_added = set(
            path_bugzilla[0] for path_bugzilla in paths_bugzilla_changed_or_added
        )
        paths_added = paths_ingested_all.difference(paths_old)
        paths_changed = paths_changed_or_added.difference(paths_added)

        path_bugzilla_data = {}
        for path_bugzilla in paths_bugzilla_ingested_all:
            path = path_bugzilla[0]
            product = path_bugzilla[1]
            component = path_bugzilla[2]
            path_bugzilla_data[path] = [product, component]

        paths_bugzilla_update_needed = []
        for path in paths_changed:
            bugzilla_component_data = self.get_or_add_bugzilla_component(path_bugzilla_data, path)
            if not bugzilla_component_data:
                continue
            path_bugzilla_update_needed = FilesBugzillaMap.objects.select_related(
                'bugzilla_component'
            ).filter(path=path)[0]
            path_bugzilla_update_needed.bugzilla_component_id = bugzilla_component_data.id
            paths_bugzilla_update_needed.append(path_bugzilla_update_needed)
        FilesBugzillaMap.objects.bulk_update(
            paths_bugzilla_update_needed, ['bugzilla_component_id'], batch_size=1000
        )

        paths_bugzilla_addition_needed = []
        for path in paths_added:
            bugzilla_component_data = self.get_or_add_bugzilla_component(path_bugzilla_data, path)
            if not bugzilla_component_data:
                continue
            file_name = (path.rsplit('/', 1))[-1]
            paths_bugzilla_addition_needed.append(
                FilesBugzillaMap(
                    path=path,
                    file_name=file_name,
                    bugzilla_component=bugzilla_component_data,
                )
            )
        FilesBugzillaMap.objects.bulk_create(paths_bugzilla_addition_needed, batch_size=1000)

        bugzilla_components_used = set(
            FilesBugzillaMap.objects.values_list('bugzilla_component_id', flat=True).distinct()
        )
        bugzilla_components_all = set(
            BugzillaComponent.objects.all().values_list('id', flat=True).distinct()
        )
        bugzilla_components_unused = bugzilla_components_all.difference(bugzilla_components_used)
        (BugzillaComponent.objects.filter(id__in=bugzilla_components_unused).delete())
