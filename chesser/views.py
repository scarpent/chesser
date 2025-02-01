from django.shortcuts import render


def home(request):
    return render(request, "home.html")


def nav(request):
    return render(request, "move_nav.html")


def subvar(request):
    return render(request, "subvar.html")
