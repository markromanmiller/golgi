from django.http import HttpResponse, FileResponse, Http404
from django.shortcuts import render, redirect
from .models import Publication, Profile
from django.core.exceptions import ValidationError


def inbox(request):
    user = request.user
    if user.is_anonymous:
        return HttpResponse("Please <a href='admin/login/?next=/'>log in</a>")

    network = Profile.objects.get(user=user).active_network
    if network is None:
        return HttpResponse("Choose an active network.")

    related_publications = [p for p in network.publication_set.filter(network_status=Publication.SUGGESTED)]
    related_publications.sort(key=lambda p : p.n_related(), reverse=True)

    context = {
        'network': network,
        'selected_publications': network.publication_set.filter(network_status=Publication.INCLUDED),
        'uploaded_publications': network.publication_set.filter(network_status=Publication.UPLOADED),
        'related_publications': related_publications
    }
    return render(request, 'crystal/rank.html', context)


def make_cites(request, publication_id):
    pub = Publication.objects.get(pk=publication_id)
    print(pub)
    pub.make_cites()
    return redirect('inbox')


def make_cited_by(request, publication_id):
    pub = Publication.objects.get(pk=publication_id)
    print(pub)
    pub.make_cited_by()
    return redirect('inbox')


def show_pdf(request, publication_id):
    pub = Publication.objects.get(pk=publication_id)
    try:
        return FileResponse(open(pub.file.path, 'rb'), content_type='application/pdf')
    except ValueError:
        raise Http404("File has not been uploaded.")


def pub_status(request, publication_pk, status):
    pub = Publication.objects.get(pk=publication_pk)
    pub.network_status = status
    try:
        pub.clean_fields()
    except ValidationError:
        return HttpResponse('Cleaning failed, could not change pub status. <a href="/">Return to home.</a>')
    pub.save()
    return redirect('inbox')

