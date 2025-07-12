import json

from django.apps import apps
from django.core.management.base import BaseCommand
from django.core.serializers import serialize


class Command(BaseCommand):
    help = "Export the chesser app data in sorted, consistent format"  # noqa: A003

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Optional output file (defaults to stdout)",
        )

    def handle(self, *args, **options):
        output_path = options["output"]
        if output_path:
            # Only write to stdout in file situation; otherwise
            # it will be included with the exported data...
            self.stdout.write("Exporting chesser app data...")

        # Dump and deserialize chesser app data
        data = []
        for model in apps.get_app_config("chesser").get_models():
            # Only want basic serialization to be loaddata-able;
            # no custom serializers or other tomfoolery
            data += json.loads(serialize("json", model.objects.all()))

        # Sort models by logical dependency order
        MODEL_ORDER = [
            "chesser.chapter",
            "chesser.variation",
            "chesser.sharedmove",
            "chesser.move",
            "chesser.quizresult",
        ]
        model_order_lookup = {model: i for i, model in enumerate(MODEL_ORDER)}

        # Warn if there are models missing from the sort order
        dumped_models = {obj["model"] for obj in data}
        unknown_models = dumped_models - set(MODEL_ORDER)

        if unknown_models:
            self.stderr.write(
                "⚠️  Warning: model(s) not in MODEL_ORDER and "
                f"will sort last: {sorted(unknown_models)}"
            )

        # Apply sort: known models in order, unknown at the end (999), pk ascending
        data.sort(
            key=lambda obj: (model_order_lookup.get(obj["model"], 999), obj["pk"])
        )

        output_data = json.dumps(data, indent=2)

        if output_path:
            with open(output_path, "w") as f:
                f.write(output_data)
            self.stdout.write(f"✅ Data written to {output_path}")
        else:
            self.stdout.write(output_data)
