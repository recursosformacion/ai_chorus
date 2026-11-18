"""Migra grupos, secciones y artículos de OSAP a Chorus.

Uso:
    OSAP_DATABASE_URL=mysql://user:pass@host/osap_api \
    CHORUS_DATABASE_URL=mysql://user:pass@host/osap_chorus \
    python scripts/migrate_osap_groups_articles.py

Es idempotente: conserva los identificadores de origen y no duplica artículos.
No borra nada en OSAP. Los artículos generales de OSAP no se migran.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

import pymysql


def connect(url: str):
    parsed = urlparse(url.replace("mysql+pymysql://", "mysql://", 1))
    return pymysql.connect(
        host=parsed.hostname or "127.0.0.1",
        port=parsed.port or 3306,
        user=parsed.username or "",
        password=parsed.password or "",
        database=(parsed.path or "/").lstrip("/"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    source_url = os.environ.get("OSAP_DATABASE_URL", "")
    target_url = os.environ.get("CHORUS_DATABASE_URL", "")
    if not source_url or not target_url:
        print("Faltan OSAP_DATABASE_URL o CHORUS_DATABASE_URL", file=sys.stderr)
        return 2
    source = connect(source_url)
    target = connect(target_url)
    stamp = now()
    counts = {"groups": 0, "members": 0, "sections": 0, "articles": 0, "media": 0}
    try:
        with source.cursor() as src, target.cursor() as dst:
            src.execute("SELECT * FROM amigos_groups")
            for group in src.fetchall():
                gid = str(group["id"])
                dst.execute(
                    """
                    INSERT INTO groups
                    (id, entity_id, name, timezone, created_by, join_code, created_at, updated_at,
                     slug, kind, description, image_url, website, email, logo_url, status,
                     editorial_mode, technical_description)
                    VALUES (%s,%s,%s,'Europe/Madrid',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE
                      name=VALUES(name), kind=VALUES(kind), description=VALUES(description),
                      image_url=VALUES(image_url), website=VALUES(website), email=VALUES(email),
                      logo_url=VALUES(logo_url), status=VALUES(status),
                      editorial_mode=VALUES(editorial_mode),
                      technical_description=VALUES(technical_description), updated_at=VALUES(updated_at)
                    """,
                    (
                        gid, gid, group["name"], group.get("created_by") or "",
                        f"LEGACY{gid[:6].upper()}", str(group.get("created_at") or stamp),
                        str(group.get("updated_at") or stamp), group.get("slug"),
                        group.get("kind") or "grupo", group.get("description"),
                        group.get("image_url"), group.get("website"), group.get("email"),
                        group.get("logo_url"), group.get("status") or "active",
                        group.get("editorial_mode") or "moderated",
                        group.get("technical_description"),
                    ),
                )
                counts["groups"] += 1

            src.execute("SELECT * FROM amigos_members")
            for member in src.fetchall():
                gid, uid = str(member["group_id"]), str(member["user_id"])
                role = "manager" if member.get("role") == "admin" else "collaborator"
                status = "active" if member.get("status") == "active" else "revoked"
                dst.execute(
                    """
                    INSERT INTO group_members
                    (id, group_id, user_sub, role, status, admin_role_id, musical_role_id,
                     section_id, joined_at, updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE
                      role=VALUES(role), status=VALUES(status),
                      admin_role_id=VALUES(admin_role_id), musical_role_id=VALUES(musical_role_id),
                      section_id=VALUES(section_id), updated_at=VALUES(updated_at)
                    """,
                    (
                        f"{gid}:{uid}", gid, uid, role, status, member.get("admin_role_id"),
                        member.get("musical_role_id"), member.get("section_id"),
                        str(member.get("created_at") or stamp), str(member.get("updated_at") or stamp),
                    ),
                )
                counts["members"] += 1

            src.execute("SELECT * FROM amigos_group_catalog")
            for item in src.fetchall():
                dst.execute(
                    """
                    INSERT INTO group_sections
                    (id, group_id, code, name, scope, parent_id, sort_order, active, created_at, updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE
                      name=VALUES(name), sort_order=VALUES(sort_order), active=VALUES(active),
                      updated_at=VALUES(updated_at)
                    """,
                    (
                        str(item["id"]), str(item["group_id"]), item["code"], item["name"],
                        item.get("scope") or "section", item.get("parent_id"),
                        int(item.get("sort_order") or 0), int(item.get("active") or 1), stamp, stamp,
                    ),
                )
                counts["sections"] += 1

            src.execute(
                "SELECT * FROM amigos_articles WHERE scope='group' AND group_id IS NOT NULL"
            )
            for article in src.fetchall():
                article_id = str(article["id"])
                dst.execute("SELECT 1 FROM groups WHERE id=%s", (str(article["group_id"]),))
                if dst.fetchone() is None:
                    print(f"omitido artículo {article_id}: grupo ausente", file=sys.stderr)
                    continue
                dst.execute(
                    """
                    INSERT INTO group_articles
                    (id, legacy_id, group_id, title, slug, summary, body, cover_url, event_date,
                     status, author_user_id, publisher_user_id, reviewed_by, reviewed_at,
                     review_note, published_at, created_at, updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE
                      title=VALUES(title), slug=VALUES(slug), summary=VALUES(summary),
                      body=VALUES(body), cover_url=VALUES(cover_url), event_date=VALUES(event_date),
                      status=VALUES(status), publisher_user_id=VALUES(publisher_user_id),
                      reviewed_by=VALUES(reviewed_by), reviewed_at=VALUES(reviewed_at),
                      review_note=VALUES(review_note), published_at=VALUES(published_at),
                      updated_at=VALUES(updated_at)
                    """,
                    (
                        article_id, article_id, str(article["group_id"]), article["title"],
                        article["slug"], article.get("summary"), article.get("body"),
                        article.get("cover_url"), str(article.get("event_date") or ""),
                        article.get("status") or "draft", str(article["author_user_id"]),
                        article.get("reviewed_by"), article.get("reviewed_by"),
                        str(article.get("reviewed_at") or "") or None,
                        article.get("review_note"), str(article.get("published_at") or "") or None,
                        str(article.get("created_at") or stamp), str(article.get("updated_at") or stamp),
                    ),
                )
                counts["articles"] += 1

            src.execute("SELECT * FROM amigos_media")
            for media in src.fetchall():
                article_id = str(media["article_id"])
                dst.execute("SELECT 1 FROM group_articles WHERE id=%s", (article_id,))
                if dst.fetchone() is None:
                    continue
                legacy_id = str(media["id"])
                dst.execute(
                    """
                    INSERT INTO group_article_media
                    (id, legacy_id, article_id, kind, url, provider, video_id, caption, credit,
                     position, created_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE
                      kind=VALUES(kind), url=VALUES(url), provider=VALUES(provider),
                      video_id=VALUES(video_id), caption=VALUES(caption), credit=VALUES(credit),
                      position=VALUES(position)
                    """,
                    (
                        f"legacy-{legacy_id}", legacy_id, article_id, media["kind"], media["url"],
                        media.get("provider"), media.get("video_id"), media.get("caption"),
                        media.get("credit"), int(media.get("position") or 0), stamp,
                    ),
                )
                counts["media"] += 1
        target.commit()
    except Exception:
        target.rollback()
        raise
    finally:
        source.close()
        target.close()
    print("Migración completada:", counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
