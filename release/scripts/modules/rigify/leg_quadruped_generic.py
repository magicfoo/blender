# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8 compliant>

import bpy
from rigify import RigifyError, get_layer_dict
from rigify_utils import bone_class_instance, copy_bone_simple, blend_bone_list, get_side_name, get_base_name, add_pole_target_bone
from rna_prop_ui import rna_idprop_ui_prop_get
from Mathutils import Vector

METARIG_NAMES = "hips", "thigh", "shin", "foot", "toe"


def metarig_template():
    # generated by rigify.write_meta_rig
    bpy.ops.object.mode_set(mode='EDIT')
    obj = bpy.context.active_object
    arm = obj.data
    bone = arm.edit_bones.new('body')
    bone.head[:] = -0.0728, -0.2427, 0.0000
    bone.tail[:] = -0.0728, -0.2427, 0.2427
    bone.roll = 0.0000
    bone.connected = False
    bone = arm.edit_bones.new('thigh')
    bone.head[:] = 0.0000, 0.0000, -0.0000
    bone.tail[:] = 0.0813, -0.2109, -0.3374
    bone.roll = -0.4656
    bone.connected = False
    bone.parent = arm.edit_bones['body']
    bone = arm.edit_bones.new('shin')
    bone.head[:] = 0.0813, -0.2109, -0.3374
    bone.tail[:] = 0.0714, -0.0043, -0.5830
    bone.roll = -0.2024
    bone.connected = True
    bone.parent = arm.edit_bones['thigh']
    bone = arm.edit_bones.new('foot')
    bone.head[:] = 0.0714, -0.0043, -0.5830
    bone.tail[:] = 0.0929, -0.0484, -0.7652
    bone.roll = -0.3766
    bone.connected = True
    bone.parent = arm.edit_bones['shin']
    bone = arm.edit_bones.new('toe')
    bone.head[:] = 0.0929, -0.0484, -0.7652
    bone.tail[:] = 0.1146, -0.1244, -0.7652
    bone.roll = -0.0000
    bone.connected = True
    bone.parent = arm.edit_bones['foot']

    bpy.ops.object.mode_set(mode='OBJECT')
    pbone = obj.pose.bones['thigh']
    pbone['type'] = 'leg_quadruped_generic'


def metarig_definition(obj, orig_bone_name):
    '''
    The bone given is the first in a chain
    Expects a chain of at least 3 children.
    eg.
        thigh -> shin -> foot -> [toe, heel]
    '''

    bone_definition = []

    orig_bone = obj.data.bones[orig_bone_name]
    orig_bone_parent = orig_bone.parent

    if orig_bone_parent is None:
        raise RigifyError("expected the thigh bone to have a parent hip bone")

    bone_definition.append(orig_bone_parent.name)
    bone_definition.append(orig_bone.name)


    bone = orig_bone
    chain = 0
    while chain < 3: # first 2 bones only have 1 child
        children = bone.children

        if len(children) != 1:
            raise RigifyError("expected the thigh bone to have 3 children without a fork")
        bone = children[0]
        bone_definition.append(bone.name) # shin, foot
        chain += 1

    if len(bone_definition) != len(METARIG_NAMES):
        raise RigifyError("internal problem, expected %d bones" % len(METARIG_NAMES))

    return bone_definition


def ik(obj, bone_definition, base_names, options):
    arm = obj.data

    # setup the existing bones, use names from METARIG_NAMES
    mt = bone_class_instance(obj, ["hips"])
    mt_chain = bone_class_instance(obj, ["thigh", "shin", "foot", "toe"])

    mt.attr_initialize(METARIG_NAMES, bone_definition)
    mt_chain.attr_initialize(METARIG_NAMES, bone_definition)

    ik_chain = mt_chain.copy(to_fmt="%s", base_names=base_names)

    ik_chain.thigh_e.connected = False
    ik_chain.thigh_e.parent = mt.hips_e

    ik_chain.foot_e.parent = None
    ik_chain.rename("foot", ik_chain.foot + "_ik")

    # keep the foot_ik as the parent
    ik_chain.toe_e.connected = False

    # must be after disconnecting the toe
    ik_chain.foot_e.align_orientation(mt_chain.toe_e)

    # children of ik_foot
    ik = bone_class_instance(obj, ["foot", "foot_roll", "foot_roll_01", "foot_roll_02", "knee_target", "foot_target"])

    ik.knee_target = add_pole_target_bone(obj, mt_chain.shin, "knee_target") #XXX - pick a better name
    ik.update()
    ik.knee_target_e.parent = mt.hips_e

    # foot roll is an interesting one!
    # plot a vector from the toe bones head, bactwards to the length of the foot
    # then align it with the foot but reverse direction.
    ik.foot_roll_e = copy_bone_simple(arm, mt_chain.toe, base_names[mt_chain.foot] + "_roll")
    ik.foot_roll = ik.foot_roll_e.name
    ik.foot_roll_e.parent = ik_chain.foot_e
    ik.foot_roll_e.translate(- (mt_chain.toe_e.vector.normalize() * mt_chain.foot_e.length))
    ik.foot_roll_e.align_orientation(mt_chain.foot_e)
    ik.foot_roll_e.tail = ik.foot_roll_e.head - ik.foot_roll_e.vector # flip
    ik.foot_roll_e.align_roll(mt_chain.foot_e.matrix.rotationPart() * Vector(0.0, 0.0, -1.0))

    # MCH-foot
    ik.foot_roll_01_e = copy_bone_simple(arm, mt_chain.foot, "MCH-" + base_names[mt_chain.foot])
    ik.foot_roll_01 = ik.foot_roll_01_e.name
    ik.foot_roll_01_e.parent = ik_chain.foot_e
    ik.foot_roll_01_e.head, ik.foot_roll_01_e.tail = mt_chain.foot_e.tail, mt_chain.foot_e.head
    ik.foot_roll_01_e.roll = ik.foot_roll_e.roll

    # ik_target, child of MCH-foot
    ik.foot_target_e = copy_bone_simple(arm, mt_chain.foot, base_names[mt_chain.foot] + "_ik_target")
    ik.foot_target = ik.foot_target_e.name
    ik.foot_target_e.parent = ik.foot_roll_01_e
    ik.foot_target_e.align_orientation(ik_chain.foot_e)
    ik.foot_target_e.length = ik_chain.foot_e.length / 2.0
    ik.foot_target_e.connected = True

    # MCH-foot.02 child of MCH-foot
    ik.foot_roll_02_e = copy_bone_simple(arm, mt_chain.foot, "MCH-%s_02" % base_names[mt_chain.foot])
    ik.foot_roll_02 = ik.foot_roll_02_e.name
    ik.foot_roll_02_e.parent = ik.foot_roll_01_e


    bpy.ops.object.mode_set(mode='OBJECT')

    mt.update()
    mt_chain.update()
    ik.update()
    ik_chain.update()

    # simple constraining of orig bones
    con = mt_chain.thigh_p.constraints.new('COPY_ROTATION')
    con.target = obj
    con.subtarget = ik_chain.thigh

    con = mt_chain.shin_p.constraints.new('COPY_ROTATION')
    con.target = obj
    con.subtarget = ik_chain.shin

    con = mt_chain.foot_p.constraints.new('COPY_ROTATION')
    con.target = obj
    con.subtarget = ik.foot_roll_02

    con = mt_chain.toe_p.constraints.new('COPY_ROTATION')
    con.target = obj
    con.subtarget = ik_chain.toe

    # others...
    con = ik.foot_roll_01_p.constraints.new('COPY_ROTATION')
    con.target = obj
    con.subtarget = ik.foot_roll


    # IK
    con = ik_chain.shin_p.constraints.new('IK')
    con.chain_length = 2
    con.iterations = 500
    con.pole_angle = -90.0 # XXX - in deg!
    con.use_tail = True
    con.use_stretch = True
    con.use_target = True
    con.use_rotation = False
    con.weight = 1.0

    con.target = obj
    con.subtarget = ik.foot_target

    con.pole_target = obj
    con.pole_subtarget = ik.knee_target


    bpy.ops.object.mode_set(mode='EDIT')

    return None, ik_chain.thigh, ik_chain.shin, ik_chain.foot, ik_chain.toe


def main(obj, bone_definition, base_names, options):
    bones_ik = ik(obj, bone_definition, base_names, options)
    return bones_ik
