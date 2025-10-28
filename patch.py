from typing import List, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(f"{__name__}")
logger.setLevel(logging.DEBUG)


def check_line(n, h):
    import string

    # ignore line endings like .,. This helps for example with extending arrays.
    if h.strip(string.whitespace + ".,") != n.strip(string.whitespace + ".,"):
        return False
    return True


class PatchUtils:
    @staticmethod
    def normalize_line_endings(text: str) -> str:
        return text.replace("\r\n", "\n").replace("\r", "\n") if text else ""

    @staticmethod
    def parse_unified_diff(diff_text: str) -> Tuple[str, str, List[str]]:
        lines = PatchUtils.normalize_line_endings(diff_text).splitlines()

        if (
            len(lines) < 3
            or not lines[0].startswith("--- ")
            or not lines[1].startswith("+++ ")
        ):
            raise ValueError("Invalid diff format")

        source_file = lines[0][4:]
        target_file = lines[1][4:]

        state = None

        hunks = []

        hunk = []
        for i, line in enumerate(lines[2:]):
            if line.startswith("@@"):
                if len(hunk) > 0:
                    hunks.append(hunk)

                hunk = []
            else:
                if len(hunk) == 0 and line.strip() == "":
                    # we'll skip first line of the patch
                    continue

                hunk.append(line)

        hunks.append(hunk)

        if source_file.startswith("a/"):
            source_file = source_file[2:]
        if target_file.startswith("b/"):
            target_file = target_file[2:]

        return source_file, target_file, hunks

    @staticmethod
    def apply_patch_to_ytext(content, diff_text: str) -> str:
        _, _, hunks = PatchUtils.parse_unified_diff(diff_text)
        content_lines = str(content).split("\n")

        totals = [None] * len(hunks)

        for hunk_index, hunk in enumerate(hunks):
            found_indices = []

            additions = 0
            deletions = 0

            # Check if hunk contains any additions or deletions
            for line in hunk:
                if len(line) > 0 and line[0] == "+":
                    additions += 1
                elif len(line) > 0 and line[0] == "-":
                    deletions += 1

            # totals[hunk_index] = {'additions': additions, 'deletions': deletions }

            if additions == 0 and deletions == 0:
                # totals[hunk_index] = { **totals[hunk_index], "error": f"Hunk {hunk_index} contains no added or deleted lines. Make sure to start the line with plus (+) to add, use minus (-) to delete." }
                continue

            # check if the patch is already applied
            def test_if_already_applied():
                is_valid = False

                for i in range(len(content_lines)):
                    j = 0

                    valid = True

                    for line in hunk:
                        if len(line) > 0 and line[0] == "+":
                            # we expect this line here, if already applied
                            if i + j < len(content_lines) and check_line(
                                content_lines[i + j], line[1:]
                            ):
                                logger.debug(
                                    f"test_if_already_applied: {line[0:]} {i + j}: valid"
                                )
                                valid = valid and True
                            else:
                                logger.debug(
                                    f"test_if_already_applied: {line[0:]} {i + j}: invalid"
                                )
                                valid = False
                        elif (
                            len(line) > 0
                            and line[0] in ["-"]
                            and i + j < len(content_lines)
                        ):
                            # we don't expect this line here, if already applied
                            if i + j < len(content_lines) and check_line(
                                content_lines[i + j], line[1:]
                            ):
                                logger.debug(
                                    f"test_if_already_applied: {line[0:]} {i + j}: invalid"
                                )
                                # valid = False
                                continue
                            else:
                                logger.debug(
                                    f"test_if_already_applied: {line[0:]} {i + j}: valid"
                                )
                                valid = valid and True
                                continue
                        elif i + j < len(content_lines) and check_line(
                            content_lines[i + j], line[0:]
                        ):
                            logger.debug(
                                f"test_if_already_applied: {line[0:]} {i + j}: valid"
                            )
                            valid = valid and True
                        elif (
                            i + j < len(content_lines)
                            and j > 0
                            and content_lines[i + j].strip() == ""
                        ):
                            # update j, not line
                            pass
                        elif j > 0 and line.strip() == "":
                            # no j update
                            continue
                        else:
                            logger.debug(
                                f"test_if_already_applied: {line[0:]} {i + j}: invalid"
                            )
                            valid = False

                        if not valid:
                            break

                        j += 1

                    if not valid:
                        continue

                    logger.debug(f"test_if_already_applied: VALID")
                    return True

                return False

            if test_if_already_applied():
                logger.warn(
                    "test_if_already_applied: The patch has been applied already"
                )
                # totals[hunk_index] = { 'error': f"Hunk {hunk_index} has been applied already"}
                continue

            # search for start of hunk
            for i in range(len(content_lines)):
                j = 0

                valid = True

                for line in hunk:
                    if i + j < len(content_lines) and check_line(
                        content_lines[i + j], line[0:]
                    ):
                        valid = valid and True
                    elif len(line) > 0 and line[0] == "+":
                        if (
                            i + j < len(content_lines)
                            and check_line(content_lines[i + j], line[1:])
                            and False
                        ):
                            valid = valid and True
                        else:
                            continue
                    elif (
                        len(line) > 0
                        and line[0] in ["-"]
                        and i + j < len(content_lines)
                    ):
                        valid = valid and check_line(content_lines[i + j], line[1:])
                    elif (
                        i + j < len(content_lines)
                        and j > 0
                        and content_lines[i + j].strip() == ""
                    ):
                        # update j, not line
                        pass
                    elif j > 0 and line.strip() == "":
                        # no j update
                        continue
                    else:
                        valid = False

                    # print("PATCH", hunk_index, "i", i,  "j", j, content_lines[i+j], line)

                    if not valid:
                        if i > 0:
                            # at least one match
                            if i + j >= len(content_lines):
                                got = "END"
                            else:
                                got = content_lines[i + j]

                            print(
                                "PATCH",
                                hunk_index,
                                "i",
                                i,
                                "j",
                                j,
                                "GOT",
                                got,
                                "EXPECTED",
                                line,
                                "HUNK",
                                hunk,
                                "NOT VALID",
                            )
                        break

                    j += 1

                if not valid:
                    continue

                print(
                    "FOUND PATCH",
                    hunk_index,
                    "i",
                    i,
                    "j",
                    j,
                    "CONTENT",
                    content_lines[i : i + j],
                    "HUNK",
                    hunk,
                    "VALID",
                )

                found_indices.append(i)

            if len(found_indices) == 0:
                print(
                    f"Hunk {hunk_index} cannot be applied: context mismatch, could not find text to update. Include the lines before and after the lines you want to add or delete (prepend with a space). When adding prefix the line with a plus (+) and when deleting prefix with a minus (-). Try to use different context, use smaller hunks. "
                )
                totals[hunk_index] = {
                    "error": f"Hunk {hunk_index} cannot be applied: context mismatch, could not find text to update. Include the lines before and after the lines you want to add or delete (prepend with a space). When adding prefix the line with a plus (+) and when deleting prefix with a minus (-). Try to use different context, use smaller hunks and verify the exact content of the file before creating the patch."
                }
                continue

            if len(found_indices) > 1:
                print(
                    f"Hunk {hunk_index} cannot be applied: multiple matching locations found: {repr(found_indices)}"
                )
                totals[hunk_index] = {
                    "error": f"Hunk {hunk_index} cannot be applied: multiple matching locations found"
                }
                continue

            i = found_indices[0]

            # the plus 1 is for line endings.
            for line in hunk:
                if i < len(content_lines) and check_line(content_lines[i], line[0:]):
                    print(f"PATCH found", line[0:])
                    i += 1
                elif len(line) > 0 and line[0] == "-":
                    pos = 0
                    for j in range(i):
                        if (a := str(content).encode("utf-8").find(b"\n", pos)) != -1:
                            pos = a + 1
                        else:
                            raise Exception("Could not find line to delete")

                    # if has line ending
                    length = len(str(content).encode("utf-8")) - pos
                    if (b := str(content).encode("utf-8").find(b"\n", pos)) != -1:
                        length = b + 1 - pos

                    print(f"PATCH deleting {pos}", pos, length)
                    del content[pos : pos + length]
                    content_lines = content_lines[:i] + content_lines[i + 1 :]
                elif len(line) > 0 and line[0] == "+":
                    if (
                        i < len(content_lines)
                        and check_line(content_lines[i], line[1:])
                        and False
                    ):
                        # line already added
                        i += 1
                        continue

                    # add

                    # convert line into pos
                    pos = 0
                    for j in range(i):
                        if (a := str(content).encode("utf-8").find(b"\n", pos)) != -1:
                            pos = a + 1
                        else:
                            pos = len(str(content).encode("utf-8"))
                            content.insert(pos, "\n")
                            pos += 1

                    print(f"PATCH adding {pos}", line[1:] + "\n")
                    content.insert(pos, line[1:] + "\n")

                    content_lines.insert(i, line[1:])
                    i += 1
                elif content_lines[i].strip() == "":
                    i += 1
                elif line.strip() == "":
                    # no j update
                    continue
                else:
                    print("\n".join(content_lines))

                    raise Exception(
                        f"Could not apply hunk {hunk_index}: could not find {line[1:]}: expected {content_lines[i]}"
                    )

        # check for errors
        errors = [
            total.get("error")
            for total in totals
            if not total is None and not total.get("error") is None
        ]
        if len(errors) > 0:
            raise Exception(
                f"Errors occured while applying patch:\n\n" + "\n".join(errors)
            )

        return "\n".join(content_lines)
