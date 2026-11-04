from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import render


def _static_file(name, content_type):
    path = Path(settings.BASE_DIR) / "static" / name
    try:
        response = FileResponse(path.open("rb"), content_type=content_type)
    except OSError as exc:
        raise Http404 from exc
    return response


def sw_js(request):
    return _static_file("sw.js", "application/javascript")


def manifest_json(request):
    return _static_file("manifest.json", "application/json")


def offline_view(request):
    return render(request, "offline.html")
