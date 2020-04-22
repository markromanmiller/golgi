from django.db import models
import tempfile, subprocess
import os
import xml.etree.ElementTree as ET
from fuzzywuzzy import process, fuzz
from django.contrib.auth.models import User
from scholarly import search_pubs_query
from urllib import parse
from django.urls import reverse


class NoPublicationFileError(ValueError):
    pass


class PublicationTag(models.Model):
    # should tags be done per network or per publication?
    # right now we're assuming all publications have their own network
    # so the reference should be to each publication
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Publication(models.Model):
    # properties of the Publication
    file = models.FileField(blank=True, max_length=500)
    author = models.CharField(max_length=500)
    title = models.CharField(max_length=500)
    year = models.CharField(max_length=10, blank=True)
    url = models.CharField(max_length=500, blank=True)

    # citation management
    cites = models.ManyToManyField("self", related_name='cited_by', blank=True, symmetrical=False)
    cites_calculated = models.BooleanField(default=False)
    cited_by_calculated = models.BooleanField(default=False)

    # every publication needs a network to keep track of it
    INCLUDED = 'INCLUDED'
    ARCHIVED = 'ARCHIVED'
    UPLOADED = 'UPLOADED'
    SUGGESTED = 'SUGGESTED'
    NETWORK_STATUS_CHOICES = (
        (INCLUDED, 'INCLUDED'),
        (ARCHIVED, 'ARCHIVED'),
        (UPLOADED, 'UPLOADED'),
        (SUGGESTED, 'SUGGESTED'),
    )
    network = models.ForeignKey("Network", blank=False, null=False, on_delete=models.CASCADE)
    network_status = models.CharField(
        max_length=10,
        choices=NETWORK_STATUS_CHOICES,
        default=SUGGESTED
    )

    # publication organization
    tags = models.ManyToManyField("PublicationTag", blank=True)
    category_tag = models.ForeignKey(
        "PublicationTag", blank=True, null=True,
        related_name='category_pubs', on_delete=models.SET_NULL
    )



    def __str__(self):
        return "{}, {}".format(self.author, self.title)

    def make_cites(self):
        if self.cites_calculated:
            # nothing to do
            return

        # make a tmp dir and tmp file
        tmpdir = tempfile.TemporaryDirectory()
        tmp_filename = os.path.join(tmpdir.name, "pub.pdf")
        tmp_copy = open(tmp_filename, 'wb')
        # TODO: what if it's not a PDF?

        # copy over the pdf
        db_file = self.file.open('rb')
        tmp_copy.write(db_file.read())
        tmp_copy.close()
        print(os.path.getsize(tmp_filename))

        # run cermine
        cermine_result = subprocess.run(
            ["java", "-cp", "cermine.jar",
             "pl.edu.icm.cermine.ContentExtractor",
             "-path", tmpdir.name,
             "-outputs", "jats"]
        )

        print(os.listdir(tmpdir.name))

        # extract results
        tree = ET.parse(os.path.join(tmpdir.name, "pub.cermxml"))

        root = tree.getroot()
        citation_list = root.find("back").find("ref-list")

        too_common = ["No Title Found", "and"]

        # only needs to be made once per paper.
        titles = [p.title for p in self.network.publication_set.all() if p.title not in too_common]

        for child in citation_list.findall('ref'):
            citation_spec = child.find("mixed-citation")
            # TODO: what other citaion types are created?
            assert (citation_spec is not None)

            # TODO: full citation spec string is also necessary
            # title
            try:
                title = citation_spec.find("article-title").text
            except AttributeError:
                title = "No Title Found"
            # year
            try:
                year = citation_spec.find("year").text
            except AttributeError:
                year = "No Year"
            # first author
            author_element = citation_spec.find("string-name")
            if author_element:
                author = " ".join([i.text for i in author_element.iter()]).strip()
            else:
                author = "Author Not Found"

            matches = process.extractBests(title, titles, scorer=fuzz.ratio, limit=1, score_cutoff=75)
            # TODO ^ allow 75 to vary, or allow list of potential matches to appear.

            # if this is a match, then link it
            if matches:
                # print(title, year, author)
                # print(matches)
                assert (len(matches) == 1)
                match_title = matches[0][0]
                matching_titles = self.network.publication_set.filter(title=match_title)
                assert (len(matching_titles) == 1)
                self.cites.add(matching_titles[0])

            else:

                # otherwise, add a new entry to the DB
                new_entry = Publication(
                    author=author,
                    title=title,
                    year=year,
                    network=self.network
                )
                new_entry.save()
                self.cites.add(new_entry)

            # self.save() # i don't want half the citations linked? idk what to do here.

        self.cites_calculated = True
        self.save()

    def make_cited_by(self):
        if self.cited_by_calculated:
            return

        # get the handle for the current paper
        # if not self.url:
        # get the google scholar url... ... oops? it's not like a url works for this...

        # Retrieve the author's data, fill-in, and print
        search_query = search_pubs_query(self.title)
        pub = next(search_query).fill()
        print(pub)

        too_common = ["No Title Found", "and"]

        titles = [p.title for p in self.network.publication_set.all() if p.title not in too_common]

        # Which papers cited that publication?
        for citation in pub.get_citedby():

            title = citation.bib['title']

            matches = process.extractBests(title, titles, scorer=fuzz.ratio, limit=1, score_cutoff=75)
            # TODO ^ allow 75 to vary, or allow list of potential matches to appear.

            # if this is a match, then link it
            if matches:
                # print(title, year, author)
                # print(matches)
                assert (len(matches) == 1)
                match_title = matches[0][0]
                matching_titles = self.network.publication_set.filter(title=match_title)
                assert (len(matching_titles) == 1)
                matching_titles[0].cites.add(self)
                matching_titles[0].save()

            else:
                try:
                    year = citation.bib['year']
                except KeyError:
                    year = ''  # don't need a year necessarily

                new_entry = Publication(
                    author=citation.bib['author'],
                    title=citation.bib['title'],
                    year=year,
                    network=self.network
                )
                new_entry.save()
                new_entry.cites.add(self)
                new_entry.save()

        self.cited_by_calculated = True
        self.save()

    def n_related(self):
        if self.is_included():
            return 0
        else:
            return (
                    sum([p.is_included() for p in self.cites.all()]) +
                    sum([p.is_included() for p in self.cited_by.all()])
            )

    def is_included(self):
        return self.network_status == Publication.INCLUDED

    def link(self):
        # if it's got a file, show the file
        if self.file:
            return reverse('show_pdf', kwargs={"publication_id": self.pk})
        # otherwise, make a Google Scholar link
        else:
            return "https://scholar.google.com/scholar?q={}".format(parse.quote(self.title, safe=""))

    def link_type(self):
        # TODO: should this merge with link? how do i put this in a logical place? view logic?
        return 'pdf' if self.file else 'search'


    def include(self):
        self.network_status = Publication.INCLUDED
        self.save()

    def archive(self):
        self.network_status = Publication.ARCHIVED
        self.save()


class Network(models.Model):
    project_title = models.CharField(max_length=500)
    owner = models.ForeignKey("Profile", on_delete=models.CASCADE)

    def __str__(self):
        return "{}".format(self.project_title)


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    active_network = models.ForeignKey(Network, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return "{}".format(self.user)
