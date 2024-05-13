#!/usr/bin/env python

import argparse
import sys
import os
from os.path import exists
from psychopy import visual, core, event, monitors, clock
from itertools import combinations
from copy import deepcopy
import yaml
import csv
import random
import re

STUDY_FILE_BASENAME="study"
RESULTS_DIR="results/"

DIST_PAIR_STR = {
    "2,3": [2,3],
    "3,4": [3,4],
    "4,5": [4,5],
    "2,4": [2,4],
    "3,5": [3,5],
    "2,5": [2,5]
}

SUBJECT_ID = None 
window = None
study = {}
graph = {}
phases = []

timing_dict = {}
def get_interval(interval_type, timing):
    if interval_type not in timing:
        raise Exception("Invalid interval type requested");
    if interval_type not in timing_dict:
        timing_dict[interval_type] = []
    if len(timing_dict[interval_type]) == 0:
        timing_dict[interval_type] = (timing[interval_type]).copy()
        random.shuffle(timing_dict[interval_type])
    return timing_dict[interval_type].pop()

######## GRAPH CALCULATION FUNCTIONS
def graph_edge_grouping_recurse(blocks, edges_per_block, edges, remaining_edges):
    if len(remaining_edges) == 0:
        return blocks
    if (len(blocks[-1]) == edges_per_block):
        blocks.append([])
    for edge in remaining_edges:
        new_blocks = deepcopy(blocks)
        new_blocks[-1].append(edge)
        if check_blocking(new_blocks, edges):
            new_remaining_edges = remaining_edges.copy()
            new_remaining_edges.remove(edge)
            ret = graph_edge_grouping_recurse(new_blocks, edges_per_block, edges, new_remaining_edges)
            if ret is not None:
                return ret
    return None

def check_blocking(blocks, edges):
    for block in blocks:
        nodes = set()
        for edge in block:
            if edges[edge][0] in nodes or edges[edge][1] in nodes:
                return False
            nodes.add(edges[edge][0])
            nodes.add(edges[edge][1])
    return True

def graph_distance_list(graph):
    nodes = range(1,len(graph["nodes"])+1)
    ret = {}
    for node in nodes:
        dist_map = {
            1: [],
            2: [],
            3: [],
            4: [],
            5: []
        }
        seen = {node}
        current = {node}
        next_nodes = set()
        dist = 1
        while len(current) > 0:
            dist_map[dist] = []
            for edge in graph["edges"]:
                othernode = -1
                if edge[0] in current and edge[1] not in seen:
                    othernode = edge[1]
                elif edge[1] in current and edge[0] not in seen:
                    othernode = edge[0]
                else:
                    continue
                seen.add(othernode)
                dist_map[dist].append(othernode)
                next_nodes.add(othernode)
            dist += 1
            current = next_nodes
            next_nodes = set()
        ret[node] = dist_map
    return ret

def graph_triad_list(graph):
    nodes = range(1,len(graph["nodes"])+1)
    ret = {}
    for dist_pair in DIST_PAIR_STR.keys():
        ret[dist_pair] = []
        for node in nodes:
            left = graph["distance_list"][node][DIST_PAIR_STR[dist_pair][0]]
            right = graph["distance_list"][node][DIST_PAIR_STR[dist_pair][1]]
            if len(left) != 0 and len(right) != 0:
                for nodeL in left:
                    for nodeR in right:
                        ret[dist_pair].append([nodeL,node,nodeR])
    return ret

def precalculate_graph_values():
    if "nodes" not in graph:
        graph["nodes"] = (graph["images"]).copy()
        random.shuffle(graph["nodes"])
    if "distance_list" not in graph:
        graph["distance_list"] = graph_distance_list(graph)
    if "triad_lists" not in graph:
        graph["triad_list"] = graph_triad_list(graph)
    if "groupings" not in graph:
        graph["groupings"] = {}

######## STUDY FILE FUNCTIONS

def study_filename(subject_id_str):
    extension = ".yaml"
    if not subject_id_str:
        return STUDY_FILE_BASENAME + extension
    return STUDY_FILE_BASENAME + "." + str(subject_id_str) + extension

def result_filename(phase_name):
    extension = ".csv"
    return RESULTS_DIR + STUDY_FILE_BASENAME + "." + str(SUBJECT_ID) + "." + "result-" + phase_name + extension

def load_params():
    for x in study["params"]:
        globals()[x] = study["params"][x]

    global IMAGE_SIZE_W
    global IMAGE_SIZE
    global UP_NODE_IMAGE_POS
    global LEFT_NODE_IMAGE_POS
    global RIGHT_NODE_IMAGE_POS

    IMAGE_SIZE_W = IMAGE_SIZE_H * VRES / HRES
    IMAGE_SIZE = (IMAGE_SIZE_W, IMAGE_SIZE_H)
    UP_NODE_IMAGE_POS=(0.0,IMAGE_OFFSET)
    LEFT_NODE_IMAGE_POS=(-IMAGE_OFFSET,0.0)
    RIGHT_NODE_IMAGE_POS=(IMAGE_OFFSET,0.0)

def load_study():
    filename = study_filename(SUBJECT_ID)
    if not exists(filename):
        filename = study_filename("")
    elif not args.cont:
        raise Exception("Trying to use existing subject_id, but 'continue' has not been specified.")
    with open(filename, 'r') as file:
        global study
        study = yaml.load(file, Loader=yaml.SafeLoader)
        global graph
        graph = study["graph"]
        precalculate_graph_values()
        load_params()
        for phase in study["phases"]:
            phases.append(Phase.gen(phase))

def write_study():
    if not SUBJECT_ID:
        raise Exception("Shouldn't write to original study file! Please provide a valid subject ID.")
    with open(study_filename(SUBJECT_ID), 'w') as file:
        yaml.dump(study, file)

def write_study_results(study):
    if not SUBJECT_ID:
        raise Exception("Shouldn't write to original study file! Please provide a valid subject ID.")
    for i in range(len(phases)):
        phase = phases[i]
        if args.phase and args.phase != phase.phase["type"]:
            continue
        with open(result_filename(str(i) + "-" + phase.phase["type"]), 'w') as file:
            csvwriter = csv.writer(file, delimiter=',')
            phase.result(csvwriter)

def sub_text(text, **kwargs):
    out = text
    for x in re.findall('#[A-Z0-9_-]+', text):
        kw = x[1:]
        if kw in kwargs:
            replace = kwargs[kw]
        elif kw in globals():
            replace = globals()[kw]
        else:
            raise Exception("Replacement text requested is not found: " + kw)
        out = out.replace(x, replace)
    return out

def draw_content(item):
    keyList = ["q", "n"]
    if item["button"] != "none":
        if item["button"] == "scanner":
            button = BUTTON_SCANNER
        elif item["button"] == 1:
            button = BUTTON_1
        elif item["button"] == 2:
            button = BUTTON_2
        elif item["button"] == 3:
            button = BUTTON_3
        keyList.append(button)
    items = []
    for elem in item["content"]:
        if "pos" not in elem:
            elem["pos"] = [0.0, 0.0]
        if "text" in elem:
            text = sub_text(elem["text"])
            vis = visual.TextBox2(window, text, pos=(elem["pos"][0], elem["pos"][1]), color=[0.0,0.0,0.0], size=[TEXTBOX_WIDTH, None], letterHeight=FONT_SIZE)
        elif "image" in elem:
            if "size" not in elem:
                elem["size"] = IMAGE_SIZE_H
            if "rot" not in elem:
                elem["rot"] = 0
            vis = visual.ImageStim(window, image="images/" + elem["image"], pos=(elem["pos"][0], elem["pos"][1]), size=(elem["size"] * VRES / HRES, elem["size"]), ori=elem["rot"])
        else:
            raise Exception("Unknown content type")
        vis.draw()
    if item["button"] != "none":
        instr_vis = visual.TextBox2(window, "Press '" + button + "' to continue", pos=(0.0, -0.8), color=[0.0,0.0,0.0], size=[TEXTBOX_WIDTH, None], alignment='center', letterHeight=FONT_SIZE)
        instr_vis.draw()
    window.flip()
    key_presses = event.waitKeys(keyList=keyList)
    return key_presses[0]

######## PHASE SPECIFIC FUNCTIONS

class Phase:
    @staticmethod
    def gen(phase):
        return globals()[phase["type"]+"Phase"](phase)
    def __init__(self, phase):
        self.phase = phase
        if "sequence" not in phase:
            phase["sequence"] = self.stim()
        pass
    def stim(self):
        pass
    def draw(self, item, n, prev_response):
        pass
    def result(self, csvwriter):
        pass
    def get_conclusion_type(self):
        return "default"
    def reset(self):
        phase = self.phase

        if "sequence" in phase:
            for item in phase["sequence"]:
                if "result" in item:
                    del item["result"]
        if "conclusion" in phase and "done" in phase["conclusion"]:
            del phase["conclusion"]["done"]

    def do(self):
        phase = self.phase

        if "repeat_count" not in phase:
            phase["repeat_count"] = 0
        phase["repeat_count"] += 1

        if "instrs" in phase and "result" not in phase["sequence"][0]:
            for instr in phase["instrs"]:
                key = draw_content(instr)
                if key == "q":
                    return "quit";
                elif key == "n":
                    return "next"
        if phase["params"]["get_ready"]:
            for i in range(3, 0, -1):
                vis = visual.TextBox2(window, "Get Ready!\n\n" + str(i), color=[0.0,0.0,0.0], size=[TEXTBOX_WIDTH, None], alignment='center', letterHeight=FONT_SIZE)
                vis.draw()
                window.flip()
                clock.wait(1)

        study_clock = clock.MonotonicClock()

        idle_count = 0
        breaks = []
        num_breaks = phase["params"]["num_breaks"]
        if num_breaks > 0:
            trials_between_breaks = len(phase["sequence"]) / (num_breaks+1)
            for i in range(num_breaks):
                breaks.append(int(trials_between_breaks * (i+1) - 1))
        
        prev_response = ''
        for i in range(len(phase["sequence"])):
            item = phase["sequence"][i]
            if "result" in item:
                prev_response = item["result"]["key_pressed"]
                continue

            self.draw(item, 0, prev_response)

            response_delay = get_interval("response_delay", phase["timing"])
            stim_delay = get_interval("stim", phase["timing"])
            isi_delay = get_interval("isi", phase["timing"])
            mw = stim_delay - response_delay
            stim_interval = clock.StaticPeriod()
            isi = clock.StaticPeriod()
            resp = clock.StaticPeriod()

            stim_interval.start(stim_delay)
            isi.start(stim_delay + isi_delay)
            window.flip()
            trial_timestamp = study_clock.getTime()

            if response_delay:
                resp.start(response_delay)
            self.draw(item, 1, prev_response)
            if response_delay:
                resp.complete()
            window.flip()
            choice_timestamp = study_clock.getTime()
            

            key_presses = event.waitKeys(maxWait=stim_delay - response_delay, keyList=[BUTTON_1, BUTTON_2, BUTTON_3, "q", "n"], timeStamped=study_clock, clearEvents=True)
            if not key_presses or len(key_presses) == 0:
                window.flip()
                key_presses = event.waitKeys(maxWait=isi_delay, keyList=[BUTTON_1, BUTTON_2, BUTTON_3, "q", "n"], timeStamped=study_clock, clearEvents=True)
                if not phase["timing"]["end_on_response"]:
                    isi.complete()
            elif not phase["timing"]["end_on_response"]:
                stim_interval.complete()
                window.flip()
                isi.complete()
            else:
                window.flip()
            print(key_presses)
            key = -1
            rt = -1
            response_timestamp = -1
            if key_presses and len(key_presses) > 0:
                (key,time) = key_presses[0]
                response_timestamp = time
            else:
                 idle_count += 1
                 if idle_count >= phase["params"]["idle_warning"]:
                    idle_count = 0
                    instr = visual.TextBox2(window, phase["params"]["idle_text"], color=[0.0,0.0,0.0], size=[TEXTBOX_WIDTH, None], letterHeight=FONT_SIZE)
                    instr.draw()
                    window.flip()
                    clock.wait(3)
            if key == "q":
                return "quit"
            elif key == "n":
                return "next"
            clock.wait(get_interval("iti", phase["timing"]))
            prev_response = key
            item["result"] = {
                "trial_timestamp": trial_timestamp,
                "choice_timestamp": choice_timestamp,
                "response_timestamp": response_timestamp,
                "key_pressed": key
            }
            write_study()
            if i in breaks:
                for i in range(60, 0, -1):
                    instr = visual.TextBox2(window, sub_text(phase["params"]["break_text"]) + "\n\n" + str(i), color=[0.0,0.0,0.0], size=[TEXTBOX_WIDTH, None], letterHeight=FONT_SIZE)
                    instr2 = visual.TextBox2(window, str(i), color=[0.0,0.0,0.0], pos=(0.0, -0.8), size=[TEXTBOX_WIDTH, None], alignment="center", letterHeight=FONT_SIZE)
                    instr.draw()
                    instr2.draw()
                    window.flip()
                    clock.wait(1)
                    if i == 45:
                        event.clearEvents()
                    elif i < 45:
                        if len(event.getKeys(keyList=[BUTTON_SCANNER])) > 0:
                            break
                if EXIT_AFTER_BREAK:
                    return "quit"
        if "conclusion" in phase and "done" not in phase["conclusion"]:
            phase["conclusion"]["done"] = True
            conc_type = self.get_conclusion_type()
            if conc_type != "default" or "default" in phase["conclusion"]:
                item = phase["conclusion"][conc_type]
                key = draw_content(item)
                if key == "q":
                    return "quit";
                elif key == "n":
                    return "next"
                elif "ret" in item:
                    return item["ret"]
        return "next"

class StudyIntroPhase(Phase):
    def stim(self):
        pass
    def draw(self, item, n, prev_response):
        if item["type"] == "example":
            a = visual.ImageStim(window, image="images/" + item["img0"], pos=LEFT_NODE_IMAGE_POS, size=IMAGE_SIZE)
            b = visual.ImageStim(window, image="images/" + item["img1"], pos=RIGHT_NODE_IMAGE_POS, size=IMAGE_SIZE)
            a.draw()
            b.draw()
        elif item["type"] == "result":
            if prev_response == BUTTON_1:
                vis = visual.TextBox2(window, sub_text(item["button_1"]), pos=(0.0,0.0), color=[0.0,0.0,0.0], size=[TEXTBOX_WIDTH, None], letterHeight=FONT_SIZE)
            else:
                vis = visual.TextBox2(window, sub_text(item["button_2"]), pos=(0.0,0.0), color=[0.0,0.0,0.0], size=[TEXTBOX_WIDTH, None], letterHeight=FONT_SIZE)
            vis.draw()
        else:
            raise Exception("Unknown StudyIntro trial type " + item["type"])
        if n > 0:
            vis = visual.TextBox2(window, sub_text(item["after"]), pos=(0.0,-0.5), color=[0.0,0.0,0.0], size=[TEXTBOX_WIDTH, None], letterHeight=FONT_SIZE)
            vis.draw()

class StudyPracticePhase(Phase):
    def stim(self):
        phase = self.phase
        rot_chance = phase["params"]["rotation_chance"]

        exp_seq = []
        for i in range(phase["params"]["practice_trials"]):
            rot = 0
            if rot_chance != 0:
                rot = random.random()
                if rot < (rot_chance/2):
                    rot = -1
                elif rot < rot_chance:
                    rot = 1
                else:
                    rot = 0
            imgs = random.sample(phase["params"]["images"], 2)
            exp_seq.append({"img0": imgs[0], "img1": imgs[1], "rot": rot, "type": "test"})
        return exp_seq
    def draw(self, item, n, prev_response):
        phase = self.phase
        if item["type"] == "test":
            ori_a = 0
            ori_b = 0
            if item["rot"] == -1:
                ori_a = 45
            elif item["rot"] == 1:
                ori_b = 45
            a = visual.ImageStim(window, image="images/" + item["img0"], pos=LEFT_NODE_IMAGE_POS, size=IMAGE_SIZE, ori=ori_a)
            b = visual.ImageStim(window, image="images/" + item["img1"], pos=RIGHT_NODE_IMAGE_POS, size=IMAGE_SIZE, ori=ori_b)
            a.draw()
            b.draw()
    def get_conclusion_type(self):
        phase = self.phase
        correct = 0
        for i in phase["sequence"]:
            if i["type"] != "test":
                continue
            if i["result"]["key_pressed"] == BUTTON_1:
                acc = i["rot"] != 0
            elif i["result"]["key_pressed"] == BUTTON_2:
                acc = i["rot"] == 0
            else:
                acc = False
            if acc:
                correct += 1
        #goodness this is ugly...only used for text replacement
        globals()["PRACTICE_SCORE"] = str(correct)
        if correct < (phase["params"]["correct_req"] * phase["params"]["practice_trials"]):
            if phase["repeat_count"] == 2:
                return "failed_2"
            else:
                return "failed"
        else:
             return "passed"
                

class StudyPhase(Phase):
    @staticmethod
    def check_sequencing(block):
        for i in range(len(block)):
            if i > 0 and block[i]["edge"] == block[i-1]["edge"] and block[i]["mirror"] == block[i]["mirror"]:
                return False
            if i > 1 and block[i]["edge"] == block[i-1]["edge"] and block[i]["edge"] == block[i-2]["edge"]:
                return False
        return True

    def stim(self):
        phase = self.phase
        global CONDITION
        if "edges_per_block" in phase["params"]:
            if phase["params"]["edges_per_block"] == 1:
                CONDITION="Interleaved"
            elif phase["params"]["edges_per_block"] == 4:
                CONDITION="Blocked"
            else:
                raise Exception("Invalid edges per block in study file")
        else:
            if CONDITION == "Interleaved":
                phase["params"]["edges_per_block"] = 1
            elif CONDITION == "Blocked":
                phase["params"]["edges_per_block"] = 4
            else:
                raise Exception("Invalid CONDITION specified")
        edges_per_block = phase["params"]["edges_per_block"]
        if edges_per_block == 1:
            graph["groupings"][str(1)] = [[*range(len(graph["edges"]))]]
        elif str(edges_per_block) not in graph["groupings"]:
            blocks = graph_edge_grouping_recurse([[]], edges_per_block, graph["edges"], [*range(len(graph["edges"]))])
            graph["groupings"][str(edges_per_block)] = blocks
            write_study()

        rot_chance = phase["params"]["rotation_chance"]
        exp_seq = []
        for block in graph["groupings"][str(phase["params"]["edges_per_block"])]:
            block_seq = []
            for edge in block:
                true = int(phase["params"]["reps_in_block"] / 2)
                false = phase["params"]["reps_in_block"] - true
                mirror = [True] * true + [False] * false
                random.shuffle(mirror)
                for i in range(phase["params"]["reps_in_block"]):
                    rot = 0
                    if rot_chance != 0:
                        rot = random.random()
                        if rot < (rot_chance/2):
                            rot = -1
                        elif rot < rot_chance:
                            rot = 1
                        else:
                            rot = 0
                    block_seq.append({"edge": edge, "mirror": mirror[i], "rot": rot})
            random.shuffle(block_seq)
            while not StudyPhase.check_sequencing(block_seq):
                random.shuffle(block_seq)
            exp_seq = exp_seq + block_seq
        return exp_seq

    def draw(self, item, n, prev_response):
        nodes = (graph["edges"][item["edge"]]).copy()
        if item["mirror"]:
            a = nodes[0]
            nodes[0] = nodes[1]
            nodes[1] = a
        ori_a = 0
        ori_b = 0
        if item["rot"] == -1:
            ori_a = 45
        elif item["rot"] == 1:
            ori_b = 45
        a = visual.ImageStim(window, image="images/" + graph["nodes"][nodes[0]-1], pos=LEFT_NODE_IMAGE_POS, size=IMAGE_SIZE, ori=ori_a)
        b = visual.ImageStim(window, image="images/" + graph["nodes"][nodes[1]-1], pos=RIGHT_NODE_IMAGE_POS, size=IMAGE_SIZE, ori=ori_b)
        a.draw()
        b.draw()

    def result(self, csvwriter):
        phase = self.phase
        rot_chance = phase["params"]["rotation_chance"]
        csvwriter.writerow( ["subject_id", "condition", "phase", "node_l", "node_r", "trial_timestamp", "response_timestamp", "response_delay", "rot", "response_key", "response", "accuracy"] )
        for item in phase["sequence"]:
            nodes = graph["edges"][item["edge"]]
            node_left = nodes[0]
            node_right = nodes[1]
            trial_timestamp = -1
            response_timestamp = -1
            response_key = -1
            response = -1
            accuracy = False
            rot = item["rot"]
            if "result" in item:
                trial_timestamp = item["result"]["trial_timestamp"]
                response_timestamp = item["result"]["response_timestamp"]
                response_key = item["result"]["key_pressed"]
                if response_key == BUTTON_1:
                    response = 0
                if response_key == BUTTON_2:
                    response = 1
                if response_key != -1:
                    if rot_chance == 0:
                        accuracy = response == 0 or response == 1
                    else:
                        if response == 0:
                            accuracy = item["rot"] != 0
                        elif response == 1:
                            accuracy = item["rot"] == 0
            csvwriter.writerow( [SUBJECT_ID, CONDITION, "Study", node_left, node_right, trial_timestamp, response_timestamp, response_timestamp - trial_timestamp, rot, response_key, response, 1 if accuracy else 0] )

class JudgementPhase(Phase):
    def check_sequencing(self, seq):
        gap = self.phase["params"]["gap_between_mirrors"]
        for i in range(len(seq) - (gap-1)):
            for j in range(i+1, i+gap):
                if seq[i]["triad"] == seq[j]["triad"]:
                    return False
        return True
    def stim(self):
        phase = self.phase
        exp_seq = []
        cnt = phase["params"]["dist_perm_cnt"]
        for dist_pair in graph["triad_list"].keys():
            shuf = graph["triad_list"][dist_pair].copy()
            random.shuffle(shuf)
            extra_cnt = 0
            if (len(shuf) * 2) < cnt:
                raise Exception("Not enough possibilities (" + str(len(shuf)) + ") to meet dist_perm_cnt requirement (" + str(cnt) + "), even w/ mirroring, for perm " + dist_par)
            elif len(shuf) < cnt:
                print("WARNING: Need to mirror distance permutations (" + str(len(shuf)) + " nonmirrored options) to meet dist_perm_cnt requirement (" + str(cnt) + ") for perm " + dist_pair)
                extra_cnt = cnt - len(shuf)
            for i in range(cnt - extra_cnt):
                mirror = random.random() < 0.5
                exp_seq.append({"triad": shuf[i], "dist": [DIST_PAIR_STR[dist_pair][0], DIST_PAIR_STR[dist_pair][1]], "mirror": mirror})
                if extra_cnt > 0:
                    exp_seq.append({"triad": shuf[i], "dist": [DIST_PAIR_STR[dist_pair][0], DIST_PAIR_STR[dist_pair][1]], "mirror": (not mirror)})
                    extra_cnt -= 1
        random.shuffle(exp_seq)
        while not self.check_sequencing(exp_seq):
            random.shuffle(exp_seq)
        return exp_seq

    def draw(self, item, n, prev_response):
        nodes = item["triad"]
        if item["mirror"]:
            a = nodes[0]
            nodes[0] = nodes[2]
            nodes[2] = a
        b = visual.ImageStim(window, image="images/" + graph["nodes"][nodes[1]-1], pos=(0,0), size=IMAGE_SIZE)
        b.draw()
        if (n > 0):
            a = visual.ImageStim(window, image="images/" + graph["nodes"][nodes[0]-1], pos=LEFT_NODE_IMAGE_POS, size=IMAGE_SIZE)
            c = visual.ImageStim(window, image="images/" + graph["nodes"][nodes[2]-1], pos=RIGHT_NODE_IMAGE_POS, size=IMAGE_SIZE)
            a.draw()
            c.draw()

    def result(self, csvwriter):
        phase = self.phase
        csvwriter.writerow( ["subject_id", "condition", "phase", "node_l", "node_c", "node_r", "dist_l", "dist_r", "trial_timestamp", "choice_timestamp", "response_timestamp", "response_delay", "response_key", "response", "accuracy"] )
        for item in phase["sequence"]:
            mirror = item["mirror"]
            if mirror:
                node_left = item["triad"][2]
                node_right = item["triad"][0]
                dist_left = item["dist"][1]
                dist_right = item["dist"][0]
            else:
                node_left = item["triad"][0]
                node_right = item["triad"][2]
                dist_left = item["dist"][0]
                dist_right = item["dist"][1]
            node_center = item["triad"][1]
            trial_timestamp = -1
            choice_timestamp = -1
            response_timestamp = -1
            response_key = -1
            response = -1
            accuracy = False
            if "result" in item:
                trial_timestamp = item["result"]["trial_timestamp"]
                choice_timestamp = item["result"]["choice_timestamp"]
                response_timestamp = item["result"]["response_timestamp"]
                response_key = item["result"]["key_pressed"]
                if response_key == BUTTON_1:
                    response = 0
                if response_key == BUTTON_2: 
                    response = 1
                if response_key != -1:
                    if response == 0:
                        accuracy = item["mirror"] == 0
                    elif response == 1:
                        accuracy = item["mirror"] == 1
            csvwriter.writerow( [SUBJECT_ID, CONDITION, "Judgement", node_left, node_center, node_right, dist_left, dist_right, trial_timestamp, choice_timestamp, response_timestamp, response_timestamp - choice_timestamp, response_key, response, 1 if accuracy else 0] )

class DirectPhase(Phase):
    def check_sequencing(self, seq):
        gap = self.phase["params"]["gap_between_mirrors"]
        for i in range(len(seq) - (gap-1)):
            for j in range(i+1, i+gap):
                if seq[i]["edge"] == seq[j]["edge"]:
                    return False
        return True
    def stim(self):
        phase = self.phase
        exp_seq = []
        for j in range(len(graph["edges"])):
            edge = graph["edges"][j]
            for i in range(2):
                node = edge[i]
                correct = edge[1 - i]
                item = {
                    "center": node,
                    "options": [{"dist": 1, "node": correct}],
                    "edge": j
                }
                valid_distances = set()
                for dist in range(2,6):
                    if len(graph["distance_list"][node][dist]) > 0:
                        valid_distances.add(dist)
                chosen_distances = random.sample(valid_distances, 2)
                for dist in chosen_distances:
                    item["options"].append({"dist": dist, "node": random.choice(graph["distance_list"][node][dist])})
                random.shuffle(item["options"])
                exp_seq.append(item)
        random.shuffle(exp_seq)
        while not self.check_sequencing(exp_seq):
            random.shuffle(exp_seq)
        return exp_seq
    def draw(self, item, n, prev_response):
        center = visual.ImageStim(window, image="images/" + graph["nodes"][item["center"]-1], pos=UP_NODE_IMAGE_POS, size=IMAGE_SIZE)
        center.draw()
        if (n > 0):
            a = visual.ImageStim(window, image="images/" + graph["nodes"][item["options"][0]["node"]-1], pos=LEFT_NODE_IMAGE_POS, size=IMAGE_SIZE)
            b = visual.ImageStim(window, image="images/" + graph["nodes"][item["options"][1]["node"]-1], pos=(0,0), size=IMAGE_SIZE)
            c = visual.ImageStim(window, image="images/" + graph["nodes"][item["options"][2]["node"]-1], pos=RIGHT_NODE_IMAGE_POS, size=IMAGE_SIZE)
            a.draw()
            b.draw()
            c.draw()
    def result(self, csvwriter):
        phase = self.phase
        csvwriter.writerow( ["subject_id", "condition", "phase", "node_c", "node_1", "node_2", "node_3", "dist_1", "dist_2", "dist_3", "trial_timestamp", "choice_timestamp", "response_timestamp", "response_delay", "response_key", "response", "accuracy"] )
        for item in phase["sequence"]:
            node_center = item["center"]
            node_1 = item["options"][0]["node"]
            node_2 = item["options"][1]["node"]
            node_3 = item["options"][2]["node"]
            dist_1 = item["options"][0]["dist"]
            dist_2 = item["options"][1]["dist"]
            dist_3 = item["options"][2]["dist"]
            trial_timestamp = -1
            choice_timestamp = -1
            response_timestamp = -1
            response_key = -1
            response = -1
            accuracy = False
            if "result" in item:
                trial_timestamp = item["result"]["trial_timestamp"]
                choice_timestamp = item["result"]["choice_timestamp"]
                response_timestamp = item["result"]["response_timestamp"]
                response_key = item["result"]["key_pressed"]
                if response_key == BUTTON_1:
                    response = 0
                elif response_key == BUTTON_2: 
                    response = 1
                elif response_key == BUTTON_3:
                    response = 2
                if response_key != -1:
                    accuracy = item["options"][response]["dist"] == 1
            csvwriter.writerow( [SUBJECT_ID, CONDITION, "Direct", node_center, node_1, node_2, node_3, dist_1, dist_2, dist_3, trial_timestamp, choice_timestamp, response_timestamp, response_timestamp - choice_timestamp, response_key, response, 1 if accuracy else 0] )

os.chdir(os.path.dirname(sys.argv[0]))

parser = argparse.ArgumentParser(description="")
parser.add_argument("subject_id")
parser.add_argument("-p", "--phase", choices=["Study", "Judgement", "Direct"], dest='phase', help="optional parameter to run a single phase")
parser.add_argument("-c", "--continue", action='store_true', dest='cont', help="optional parameter to run a single phase")
args = parser.parse_args()

SUBJECT_ID = args.subject_id
if int(SUBJECT_ID) % 2 == 0:
    CONDITION = "Interleaved"
else:
    CONDITION = "Blocked"
print(f"Selected condition {CONDITION}")

load_study()

monitor = monitors.Monitor("expMonitor", width=SCREENWIDTH)
monitor.setSizePix((HRES, VRES))
monitor.saveMon()
window = visual.Window([HRES, VRES], allowGUI=True, monitor=monitor, units="norm", color="white", fullscr=True, screen=0)

for phase in phases:
    if args.phase and args.phase != phase.phase["type"]:
        continue
    ret = "repeat"
    while ret == "repeat":
        ret = phase.do()
        if ret == "repeat":
            phase.reset()
    if ret == "quit":
        break

write_study_results(study)
