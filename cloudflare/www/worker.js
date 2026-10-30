// www.houseofaspirants.in -> houseofaspirants.in (same path and query), 301.
export default {
  fetch(request) {
    const url = new URL(request.url);
    url.hostname = "houseofaspirants.in";
    return Response.redirect(url.toString(), 301);
  },
};
