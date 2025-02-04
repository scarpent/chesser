from django.shortcuts import render


def home(request):
    return render(request, "home.html")


def nav(request):
    return render(request, "move_nav.html")


def practice(request):
    return render(request, "practice.html")
