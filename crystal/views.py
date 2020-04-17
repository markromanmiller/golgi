from django.http import HttpResponse
from django.shortcuts import render, redirect
from .models import Publication, Profile


def index(request):
    return HttpResponse("Hello, world. You're at the Golgi index.")


def rank(request):
    # TODO: switch over to a user-based system where each 
    # user has a single active project they're asking about?

    user = request.user
    if user is None:
        return HttpResponse("Please log in")

    network = Profile.objects.get(user=user).active_network
    if network is None:
        return HttpResponse("Choose an active network.")

    related_publications = [p for p in network.publication_set.all() if p.n_related()]
    related_publications.sort(key=lambda p : p.n_related(), reverse=True)

    context = {
        'selected_publications': network.publication_set.filter(network_status=Publication.INCLUDED),
        'related_publications': related_publications
    }
    return render(request, 'crystal/rank.html', context)


def make_cites(request, publication_id):
    pub = Publication.objects.get(pk=publication_id)
    print(pub)
    pub.make_cites()
    return redirect('rank')

def make_cited_by(request, publication_id):
    pub = Publication.objects.get(pk=publication_id)
    print(pub)
    pub.make_cited_by()
    return redirect('rank')


