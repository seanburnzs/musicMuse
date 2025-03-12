Get Album

OAuth 2.0
Get Spotify catalog information for a single album.

Important policy notes
Spotify content may not be downloaded
Keep visual content in its original form
Ensure content attribution
Request

GET
/albums/{id}
id
string
Required
The Spotify ID of the album.

Example: 4aawyAB9vmqN3uQ7FjRGTy
market
string
An ISO 3166-1 alpha-2 country code. If a country code is specified, only content that is available in that market will be returned.
If a valid user access token is specified in the request header, the country associated with the user account will take priority over this parameter.
Note: If neither market or user country are provided, the content is considered unavailable for the client.
Users can view the country that is associated with their account in the account settings.

Example: market=ES
Response
200
401
403
429
An album

album_type
string
Required
The type of the album.

Allowed values: "album", "single", "compilation"
Example: "compilation"
total_tracks
integer
Required
The number of tracks in the album.

Example: 9
available_markets
array of strings
Required
The markets in which the album is available: ISO 3166-1 alpha-2 country codes. NOTE: an album is considered available in a market when at least 1 of its tracks is available in that market.

Example: ["CA","BR","IT"]

external_urls
object
Required
Known external URLs for this album.

spotify
string
The Spotify URL for the object.

href
string
Required
A link to the Web API endpoint providing full details of the album.

id
string
Required
The Spotify ID for the album.

Example: "2up3OPMp9Tb4dAKM2erWXQ"

images
array of ImageObject
Required
The cover art for the album in various sizes, widest first.

url
string
Required
The source URL of the image.

Example: "https://i.scdn.co/image/ab67616d00001e02ff9ca10b55ce82ae553c8228"
height
integer
Required
Nullable
The image height in pixels.

Example: 300
width
integer
Required
Nullable
The image width in pixels.

Example: 300
name
string
Required
The name of the album. In case of an album takedown, the value may be an empty string.

release_date
string
Required
The date the album was first released.

Example: "1981-12"
release_date_precision
string
Required
The precision with which release_date value is known.

Allowed values: "year", "month", "day"
Example: "year"

restrictions
object
Included in the response when a content restriction is applied.

reason
string
The reason for the restriction. Albums may be restricted if the content is not available in a given market, to the user's subscription type, or when the user's account is set to not play explicit content. Additional reasons may be added in the future.

Allowed values: "market", "product", "explicit"
type
string
Required
The object type.

Allowed values: "album"
uri
string
Required
The Spotify URI for the album.

Example: "spotify:album:2up3OPMp9Tb4dAKM2erWXQ"

artists
array of SimplifiedArtistObject
Required
The artists of the album. Each artist object includes a link in href to more detailed information about the artist.


external_urls
object
Known external URLs for this artist.

href
string
A link to the Web API endpoint providing full details of the artist.

id
string
The Spotify ID for the artist.

name
string
The name of the artist.

type
string
The object type.

Allowed values: "artist"
uri
string
The Spotify URI for the artist.


tracks
object
Required
The tracks of the album.

href
string
Required
A link to the Web API endpoint returning the full result of the request

Example: "https://api.spotify.com/v1/me/shows?offset=0&limit=20"
limit
integer
Required
The maximum number of items in the response (as set in the query or by default).

Example: 20
next
string
Required
Nullable
URL to the next page of items. ( null if none)

Example: "https://api.spotify.com/v1/me/shows?offset=1&limit=1"
offset
integer
Required
The offset of the items returned (as set in the query or by default)

Example: 0
previous
string
Required
Nullable
URL to the previous page of items. ( null if none)

Example: "https://api.spotify.com/v1/me/shows?offset=1&limit=1"
total
integer
Required
The total number of items available to return.

Example: 4

items
array of SimplifiedTrackObject
Required

copyrights
array of CopyrightObject
Required
The copyright statements of the album.

text
string
The copyright text for this content.

type
string
The type of copyright: C = the copyright, P = the sound recording (performance) copyright.


external_ids
object
Required
Known external IDs for the album.

isrc
string
International Standard Recording Code

ean
string
International Article Number

upc
string
Universal Product Code

genres
array of strings
Required
Deprecated
Deprecated The array is always empty.

Example: []
label
string
Required
The label associated with the album.

popularity
integer
Required
The popularity of the album. The value will be between 0 and 100, with 100 being the most popular.



endpoint
https://api.spotify.com/v1/albums/{id}
id
4aawyAB9vmqN3uQ7FjRGTy
market
ES
Request sample

cURL

Wget

HTTPie
curl --request GET \
  --url https://api.spotify.com/v1/albums/4aawyAB9vmqN3uQ7FjRGTy \
  --header 'Authorization: Bearer 1POdFZRZbvb...qqillRxMr2z'
Response sample
{
  "album_type": "compilation",
  "total_tracks": 9,
  "available_markets": ["CA", "BR", "IT"],
  "external_urls": {
    "spotify": "string"
  },
  "href": "string",
  "id": "2up3OPMp9Tb4dAKM2erWXQ",
  "images": [
    {
      "url": "https://i.scdn.co/image/ab67616d00001e02ff9ca10b55ce82ae553c8228",
      "height": 300,
      "width": 300
    }
  ],
  "name": "string",
  "release_date": "1981-12",
  "release_date_precision": "year",
  "restrictions": {
    "reason": "market"
  },
  "type": "album",
  "uri": "spotify:album:2up3OPMp9Tb4dAKM2erWXQ",
  "artists": [
    {
      "external_urls": {
        "spotify": "string"
      },
      "href": "string",
      "id": "string",
      "name": "string",
      "type": "artist",
      "uri": "string"
    }
  ],
  "tracks": {
    "href": "https://api.spotify.com/v1/me/shows?offset=0&limit=20",
    "limit": 20,
    "next": "https://api.spotify.com/v1/me/shows?offset=1&limit=1",
    "offset": 0,
    "previous": "https://api.spotify.com/v1/me/shows?offset=1&limit=1",
    "total": 4,
    "items": [
      {
        "artists": [
          {
            "external_urls": {
              "spotify": "string"
            },
            "href": "string",
            "id": "string",
            "name": "string",
            "type": "artist",
            "uri": "string"
          }
        ],
        "available_markets": ["string"],
        "disc_number": 0,
        "duration_ms": 0,
        "explicit": false,
        "external_urls": {
          "spotify": "string"
        },
        "href": "string",
        "id": "string",
        "is_playable": false,
        "linked_from": {
          "external_urls": {
            "spotify": "string"
          },
          "href": "string",
          "id": "string",
          "type": "string",
          "uri": "string"
        },
        "restrictions": {
          "reason": "string"
        },
        "name": "string",
        "preview_url": "string",
        "track_number": 0,
        "type": "string",
        "uri": "string",
        "is_local": false
      }
    ]
  },
  "copyrights": [
    {
      "text": "string",
      "type": "string"
    }
  ],
  "external_ids": {
    "isrc": "string",
    "ean": "string",
    "upc": "string"
  },
  "genres": [],
  "label": "string",
  "popularity": 0
}



Get Artist

OAuth 2.0
Get Spotify catalog information for a single artist identified by their unique Spotify ID.

Important policy notes
Spotify content may not be downloaded
Keep visual content in its original form
Ensure content attribution
Request

GET
/artists/{id}
id
string
Required
The Spotify ID of the artist.

Example: 0TnOYISbd1XYRBk9myaseg
Response
200
401
403
429
An artist


external_urls
object
Known external URLs for this artist.

spotify
string
The Spotify URL for the object.


followers
object
Information about the followers of the artist.

href
string
Nullable
This will always be set to null, as the Web API does not support it at the moment.

total
integer
The total number of followers.

genres
array of strings
A list of the genres the artist is associated with. If not yet classified, the array is empty.

Example: ["Prog rock","Grunge"]
href
string
A link to the Web API endpoint providing full details of the artist.

id
string
The Spotify ID for the artist.


images
array of ImageObject
Images of the artist in various sizes, widest first.

url
string
Required
The source URL of the image.

Example: "https://i.scdn.co/image/ab67616d00001e02ff9ca10b55ce82ae553c8228"
height
integer
Required
Nullable
The image height in pixels.

Example: 300
width
integer
Required
Nullable
The image width in pixels.

Example: 300
name
string
The name of the artist.

popularity
integer
The popularity of the artist. The value will be between 0 and 100, with 100 being the most popular. The artist's popularity is calculated from the popularity of all the artist's tracks.

type
string
The object type.

Allowed values: "artist"
uri
string
The Spotify URI for the artist.

endpoint
https://api.spotify.com/v1/artists/{id}
id
0TnOYISbd1XYRBk9myaseg
Request sample

cURL

Wget

HTTPie
wget --quiet \
  --method GET \
  --header 'Authorization: Bearer 1POdFZRZbvb...qqillRxMr2z' \
  --output-document \
  - https://api.spotify.com/v1/artists/0TnOYISbd1XYRBk9myaseg
Response sample
{
  "external_urls": {
    "spotify": "string"
  },
  "followers": {
    "href": "string",
    "total": 0
  },
  "genres": ["Prog rock", "Grunge"],
  "href": "string",
  "id": "string",
  "images": [
    {
      "url": "https://i.scdn.co/image/ab67616d00001e02ff9ca10b55ce82ae553c8228",
      "height": 300,
      "width": 300
    }
  ],
  "name": "string",
  "popularity": 0,
  "type": "artist",
  "uri": "string"
}

Get Track

OAuth 2.0
Get Spotify catalog information for a single track identified by its unique Spotify ID.

Important policy notes
Spotify content may not be downloaded
Keep visual content in its original form
Ensure content attribution
Spotify content may not be used to train machine learning or AI model
Request

GET
/tracks/{id}
id
string
Required
The Spotify ID for the track.

Example: 11dFghVXANMlKmJXsNCbNl
market
string
An ISO 3166-1 alpha-2 country code. If a country code is specified, only content that is available in that market will be returned.
If a valid user access token is specified in the request header, the country associated with the user account will take priority over this parameter.
Note: If neither market or user country are provided, the content is considered unavailable for the client.
Users can view the country that is associated with their account in the account settings.

Example: market=ES
Response
200
401
403
429
A track


album
object
The album on which the track appears. The album object includes a link in href to full information about the album.

album_type
string
Required
The type of the album.

Allowed values: "album", "single", "compilation"
Example: "compilation"
total_tracks
integer
Required
The number of tracks in the album.

Example: 9
available_markets
array of strings
Required
The markets in which the album is available: ISO 3166-1 alpha-2 country codes. NOTE: an album is considered available in a market when at least 1 of its tracks is available in that market.

Example: ["CA","BR","IT"]

external_urls
object
Required
Known external URLs for this album.

href
string
Required
A link to the Web API endpoint providing full details of the album.

id
string
Required
The Spotify ID for the album.

Example: "2up3OPMp9Tb4dAKM2erWXQ"

images
array of ImageObject
Required
The cover art for the album in various sizes, widest first.

name
string
Required
The name of the album. In case of an album takedown, the value may be an empty string.

release_date
string
Required
The date the album was first released.

Example: "1981-12"
release_date_precision
string
Required
The precision with which release_date value is known.

Allowed values: "year", "month", "day"
Example: "year"

restrictions
object
Included in the response when a content restriction is applied.

type
string
Required
The object type.

Allowed values: "album"
uri
string
Required
The Spotify URI for the album.

Example: "spotify:album:2up3OPMp9Tb4dAKM2erWXQ"

artists
array of SimplifiedArtistObject
Required
The artists of the album. Each artist object includes a link in href to more detailed information about the artist.


artists
array of SimplifiedArtistObject
The artists who performed the track. Each artist object includes a link in href to more detailed information about the artist.


external_urls
object
Known external URLs for this artist.

href
string
A link to the Web API endpoint providing full details of the artist.

id
string
The Spotify ID for the artist.

name
string
The name of the artist.

type
string
The object type.

Allowed values: "artist"
uri
string
The Spotify URI for the artist.

available_markets
array of strings
A list of the countries in which the track can be played, identified by their ISO 3166-1 alpha-2 code.

disc_number
integer
The disc number (usually 1 unless the album consists of more than one disc).

duration_ms
integer
The track length in milliseconds.

explicit
boolean
Whether or not the track has explicit lyrics ( true = yes it does; false = no it does not OR unknown).


external_ids
object
Known external IDs for the track.

isrc
string
International Standard Recording Code

ean
string
International Article Number

upc
string
Universal Product Code


external_urls
object
Known external URLs for this track.

spotify
string
The Spotify URL for the object.

href
string
A link to the Web API endpoint providing full details of the track.

id
string
The Spotify ID for the track.

is_playable
boolean
Part of the response when Track Relinking is applied. If true, the track is playable in the given market. Otherwise false.


linked_from
object
Part of the response when Track Relinking is applied, and the requested track has been replaced with different track. The track in the linked_from object contains information about the originally requested track.


restrictions
object
Included in the response when a content restriction is applied.

reason
string
The reason for the restriction. Supported values:

market - The content item is not available in the given market.
product - The content item is not available for the user's subscription type.
explicit - The content item is explicit and the user's account is set to not play explicit content.
Additional reasons may be added in the future. Note: If you use this field, make sure that your application safely handles unknown values.

name
string
The name of the track.

popularity
integer
The popularity of the track. The value will be between 0 and 100, with 100 being the most popular.
The popularity of a track is a value between 0 and 100, with 100 being the most popular. The popularity is calculated by algorithm and is based, in the most part, on the total number of plays the track has had and how recent those plays are.
Generally speaking, songs that are being played a lot now will have a higher popularity than songs that were played a lot in the past. Duplicate tracks (e.g. the same track from a single and an album) are rated independently. Artist and album popularity is derived mathematically from track popularity. Note: the popularity value may lag actual popularity by a few days: the value is not updated in real time.

preview_url
string
Nullable
Deprecated
A link to a 30 second preview (MP3 format) of the track. Can be null

Important policy note
Spotify Audio preview clips can not be a standalone service
track_number
integer
The number of the track. If an album has several discs, the track number is the number on the specified disc.

type
string
The object type: "track".

Allowed values: "track"
uri
string
The Spotify URI for the track.

is_local
boolean
Whether or not the track is from a local file.

endpoint
https://api.spotify.com/v1/tracks/{id}
id
11dFghVXANMlKmJXsNCbNl
market
ES
Request sample

cURL

Wget

HTTPie
http GET https://api.spotify.com/v1/tracks/11dFghVXANMlKmJXsNCbNl \
  Authorization:'Bearer 1POdFZRZbvb...qqillRxMr2z'
Response sample
{
  "album": {
    "album_type": "compilation",
    "total_tracks": 9,
    "available_markets": ["CA", "BR", "IT"],
    "external_urls": {
      "spotify": "string"
    },
    "href": "string",
    "id": "2up3OPMp9Tb4dAKM2erWXQ",
    "images": [
      {
        "url": "https://i.scdn.co/image/ab67616d00001e02ff9ca10b55ce82ae553c8228",
        "height": 300,
        "width": 300
      }
    ],
    "name": "string",
    "release_date": "1981-12",
    "release_date_precision": "year",
    "restrictions": {
      "reason": "market"
    },
    "type": "album",
    "uri": "spotify:album:2up3OPMp9Tb4dAKM2erWXQ",
    "artists": [
      {
        "external_urls": {
          "spotify": "string"
        },
        "href": "string",
        "id": "string",
        "name": "string",
        "type": "artist",
        "uri": "string"
      }
    ]
  },
  "artists": [
    {
      "external_urls": {
        "spotify": "string"
      },
      "href": "string",
      "id": "string",
      "name": "string",
      "type": "artist",
      "uri": "string"
    }
  ],
  "available_markets": ["string"],
  "disc_number": 0,
  "duration_ms": 0,
  "explicit": false,
  "external_ids": {
    "isrc": "string",
    "ean": "string",
    "upc": "string"
  },
  "external_urls": {
    "spotify": "string"
  },
  "href": "string",
  "id": "string",
  "is_playable": false,
  "linked_from": {
  },
  "restrictions": {
    "reason": "string"
  },
  "name": "string",
  "popularity": 0,
  "preview_url": "string",
  "track_number": 0,
  "type": "track",
  "uri": "string",
  "is_local": false
}