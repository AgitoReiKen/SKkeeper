##
##  GPL License
##
##  Blender Addon | SKkeeper
##  Copyright (C) 2020  Johannes Rauch
##
##  This program is free software: you can redistribute it and/or modify
##  it under the terms of the GNU General Public License as published by
##  the Free Software Foundation, either version 3 of the License, or
##  (at your option) any later version.
##
##  This program is distributed in the hope that it will be useful,
##  but WITHOUT ANY WARRANTY; without even the implied warranty of
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##  GNU General Public License for more details.
##
##  You should have received a copy of the GNU General Public License
##  along with this program.  If not, see <https://www.gnu.org/licenses/>.

bl_info = {
    "name": "SKkeeper",
    "author": "Johannes Rauch, AgitoReiKen",
    "version": (2, 0),
    "blender": (4, 1, 0),
    "location": "Object > Apply, Object > Animation",
    "description": "Applies modifiers and keeps shapekeys",
    "category": "Utility",
    "wiki_url": "https://github.com/agitoreiken/SKkeeper",
}

import bpy
from bpy.types import Operator, PropertyGroup
from bpy.props import BoolProperty, CollectionProperty


def copy_object(obj, times=1, offset=0):
    # TODO: maybe get the collection of the source and link the object to
    # that collection instead of the scene main collection

    objects = []
    for i in range(0, times):
        copy_obj = obj.copy()
        copy_obj.data = obj.data.copy()
        copy_obj.name = obj.name + "_shapekey_" + str(i + 1)
        copy_obj.location.x += offset * (i + 1)

        bpy.context.collection.objects.link(copy_obj)
        objects.append(copy_obj)

    return objects


def duplicate_object(obj, times=1, offset=0):
    """duplicates the given object and its data"""

    # DEPRECATED >> USE copy_object instead

    for o in bpy.context.scene.objects:
        o.select_set(False)

    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    objects = []
    for i in range(0, times):
        bpy.ops.object.duplicate()
        copy = bpy.context.active_object
        copy.name = obj.name + "_shapekey_" + str(i + 1)
        copy.location.x += offset
        objects.append(copy)

    return objects


def apply_shapekey(obj, sk_keep):
    """deletes all shapekeys except the one with the given index"""
    shapekeys = obj.data.shape_keys.key_blocks

    # check for valid index
    if sk_keep < 0 or sk_keep > len(shapekeys):
        return

    # remove all other shapekeys
    for i in reversed(range(0, len(shapekeys))):
        if i != sk_keep:
            obj.shape_key_remove(shapekeys[i])

    # remove the chosen one and bake it into the object
    obj.shape_key_remove(shapekeys[0])


def apply_modifiers(self, obj):
    """applies all modifiers in order"""
    # now uses object.convert to circumvent errors with disabled modifiers

    modifiers = obj.modifiers
    for modifier in modifiers:
        if modifier.type == "SUBSURF":
            modifier.show_only_control_edges = False

    for o in bpy.context.scene.objects:
        o.select_set(False)

    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    # bpy.ops.object.convert(target="MESH")

    for mod in modifiers:
        if mod.type != "ARMATURE":
            try:
                bpy.ops.object.modifier_apply(modifier=mod.name)
            except:
                self.report(
                    {"INFO"},
                    f"Removed invalid modifier {mod.name} ({mod.type}) from {obj.name}",
                )
                bpy.ops.object.modifier_remove(modifier=mod.name)


def remove_modifiers(obj):
    """removes all modifiers from the object"""

    for i in reversed(range(0, len(obj.modifiers))):
        modifier = obj.modifiers[i]
        obj.modifiers.remove(modifier)


def add_objs_shapekeys(destination, sources):
    """takes an array of objects and adds them as shapekeys to the destination object"""
    for o in bpy.context.scene.objects:
        o.select_set(False)

    for src in sources:
        src.select_set(True)

    bpy.context.view_layer.objects.active = destination
    bpy.ops.object.join_shapes()


class SK_OT_apply_mods(Operator):
    """Applies modifiers and keeps shapekeys for all selected meshes"""

    bl_idname = "sk.apply_mods"
    bl_label = "All Modifiers"
    bl_options = {"REGISTER", "UNDO"}
    action: bpy.props.EnumProperty(
        name="Action",
        description="Choose what to apply",
        items=[
            ("ALL_MODIFIERS", "All Modifiers", "Apply all modifiers"),
            (
                "ALL_MODIFIERS_WITH_SHAPEKEYS",
                "All Modifiers with Shape Keys",
                "Apply all modifiers and retain shape keys",
            ),
        ],
        default="ALL_MODIFIERS",
    )  # type: ignore

    def validate_input(self):
        if len(self.objects) == 0:
            self.report(
                {"ERROR"}, "No Active object. Please select at least 1 mesh object"
            )
            return False
        return True

    def execute(self, context):
        self.objects = [obj for obj in context.selected_objects if obj.type == "MESH"]
        if not self.validate_input():
            return {"CANCELLED"}

        if self.action == "ALL_MODIFIERS":
            self.apply_all_modifiers(context)
        elif self.action == "ALL_MODIFIERS_WITH_SHAPEKEYS":
            self.apply_all_modifiers_with_sk(context)

        return {"FINISHED"}

    def apply_all_modifiers_with_sk(self, context):
        for obj in self.objects:
            if obj.data.shape_keys is None:
                apply_modifiers(self, obj)
                continue

            # create receiving object that will contain all collapsed shapekeys
            receiver = copy_object(obj, times=1, offset=0)[0]
            receiver.name = "sk_receiver"
            apply_shapekey(receiver, 0)
            apply_modifiers(self, receiver)

            for i in range(1, len(obj.data.shape_keys.key_blocks)):
                obj_sk = obj.data.shape_keys.key_blocks[i]
                # copy of baseobject / blendshape donor
                blendshape = copy_object(obj, times=1, offset=0)[0]
                apply_shapekey(blendshape, i)
                apply_modifiers(self, blendshape)

                # add the copy as a blendshape to the receiver
                add_objs_shapekeys(receiver, [blendshape])

                # restore the shapekey name
                sk = receiver.data.shape_keys.key_blocks[i]
                sk.name = obj_sk.name

                # delete the blendshape donor and its mesh datablock (save memory)
                mesh_data = blendshape.data
                bpy.data.objects.remove(blendshape)
                bpy.data.meshes.remove(mesh_data)

            # rename id, copy action, drivers, nla tracks
            # proper sk.id_data name, applied after object has been deleted to avoid .000 postfix
            skidname = f"{obj.name}.SK"

            objskid = obj.data.shape_keys.key_blocks[0].id_data
            skid = receiver.data.shape_keys.key_blocks[0].id_data
            objskid.animation_data_create()
            skid.animation_data_create()
            obj_anim_data = objskid.animation_data
            anim_data = skid.animation_data
            if obj_anim_data and obj_anim_data.nla_tracks:
                for track in obj_anim_data.nla_tracks:
                    print(f"Track Name: {track.name}")
                    print(f"Muted: {track.mute}")
                    print(f"Is Solo: {track.is_solo}")

                    # Iterate through each strip in the track
                    for strip in track.strips:
                        print(f"  Strip Name: {strip.name}")
                        print(
                            f"  Action: {strip.action.name if strip.action else 'None'}"
                        )
                        print(f"  Frame Start: {strip.frame_start}")
                        print(f"  Frame End: {strip.frame_end}")
                        print(f"  Use Animated Time: {strip.use_animated_time}")

            if anim_data and anim_data.nla_tracks:
                for track in anim_data.nla_tracks:
                    print(f"Track Name: {track.name}")
                    print(f"Muted: {track.mute}")
                    print(f"Is Solo: {track.is_solo}")

                    # Iterate through each strip in the track
                    for strip in track.strips:
                        print(f"  Strip Name: {strip.name}")
                        print(
                            f"  Action: {strip.action.name if strip.action else 'None'}"
                        )
                        print(f"  Frame Start: {strip.frame_start}")
                        print(f"  Frame End: {strip.frame_end}")
                        print(f"  Use Animated Time: {strip.use_animated_time}")

            # copy action
            if objskid.animation_data.action:
                skid.animation_data.action = objskid.animation_data.action.copy()

            # copy drivers
            if objskid.animation_data.drivers:
                for driver in objskid.animation_data.drivers:
                    new_driver = skid.driver_add(driver.data_path)
                    new_driver.driver.type = driver.driver.type
                    new_driver.mute = driver.mute
                    new_driver.driver.expression = driver.driver.expression
                    new_driver.driver.use_self = driver.driver.use_self

                    # Copy all variables of the driver
                    for var in driver.driver.variables:
                        new_var = new_driver.driver.variables.new()
                        new_var.name = var.name
                        new_var.type = var.type

                        # Copy targets
                        for i, target in enumerate(var.targets):
                            new_var.targets[i].id = target.id
                            new_var.targets[i].data_path = target.data_path
                            new_var.targets[i].bone_target = target.bone_target
                            new_var.targets[i].transform_space = target.transform_space
                            new_var.targets[i].transform_type = target.transform_type

            # copy nla tracks
            if objskid.animation_data.nla_tracks:
                for track in objskid.animation_data.nla_tracks:
                    new_track = skid.animation_data.nla_tracks.new()
                    new_track.name = track.name
                    new_track.is_solo = track.is_solo
                    new_track.mute = track.mute

                    # Copy NLA strips
                    for strip in track.strips:
                        new_strip = new_track.strips.new(
                            strip.name, int(strip.frame_start), strip.action
                        )
                        # new_strip.action_frame_start = strip.action_frame_start
                        # new_strip.action_frame_end = strip.action_frame_end
                        new_strip.blend_in = strip.blend_in
                        new_strip.blend_out = strip.blend_out
                        new_strip.use_auto_blend = strip.use_auto_blend
                        new_strip.extrapolation = strip.extrapolation
                        # new_strip.frame_start = strip.frame_start
                        # new_strip.frame_end = strip.frame_end

            # delete the original and its mesh data
            orig_name = obj.name
            orig_data = obj.data
            bpy.data.objects.remove(obj)
            bpy.data.meshes.remove(orig_data)

            skid.name = skidname

            # rename the receiver
            receiver.name = orig_name

    def apply_all_modifiers(self, context):
        self.next_selection = []
        for obj in self.objects:
            # VALID OBJECT
            if obj.data.shape_keys is not None:
                self.next_selection.append(obj)
                continue
            apply_modifiers(self, obj)

        bpy.ops.object.select_all(action="DESELECT")

        for obj in self.next_selection:
            obj.select_set(True)

        return {"FINISHED"}


class SK_OT_bake_shapekey_animation(Operator):
    """Bakes shapekey values into keyframes"""

    bl_idname = "sk.bake_shapekey_animation"
    bl_label = "Bake shapekey animation into keyframes"
    bl_options = {"REGISTER", "UNDO"}

    def validate_input(self):
        # check for valid selection
        if len(self.objects) == 0:
            self.report(
                {"ERROR"},
                "No appropriate mesh selected. Please select at least 1 mesh with shape keys",
            )
            return False
        return True

    def execute(self, context):
        self.objects = [
            obj
            for obj in context.selected_objects
            if obj.type == "MESH" and obj.data.shape_keys is not None
        ]
        if not self.validate_input():
            return {"CANCELLED"}

        context = bpy.context
        scene = context.scene

        for frame in range(scene.frame_start, scene.frame_end + 1):
            scene.frame_set(frame)
            for obj in self.objects:
                for fcurve in obj.data.shape_keys.animation_data.drivers.values():
                    obj.data.shape_keys.keyframe_insert(fcurve.data_path, frame=frame)

        return {"FINISHED"}


class SK_OT_toggle_shapekeys_drivers(Operator):
    """Toggles shapekeys drivers"""

    bl_idname = "sk.toggle_shapekeys_drivers"
    bl_label = "Toggle shapekey(s) drivers"
    bl_options = {"REGISTER", "UNDO"}
    action: bpy.props.EnumProperty(
        name="Action",
        description="Choose an action to perform",
        items=[
            ("TOGGLE", "Toggle", "Toggle the drivers"),
            ("MUTE", "Mute", "Mute the drivers"),
            ("UNMUTE", "Unmute", "Unmute the drivers"),
        ],
        default="TOGGLE",
    )  # type: ignore

    def validate_input(self):
        # check for valid selection
        if len(self.objects) == 0:
            self.report(
                {"ERROR"},
                "No appropriate mesh selected. Please select at least 1 mesh with shape key that has driver on it",
            )
            return False
        return True

    def execute(self, context):
        self.objects = [
            obj
            for obj in context.selected_objects
            if obj.type == "MESH" and obj.data.shape_keys is not None
        ]
        if not self.validate_input():
            return {"CANCELLED"}

        context = bpy.context
        num_toggled = 0
        num_toggled_obj = 0
        for obj in self.objects:
            if obj.data.shape_keys.id_data.animation_data is None:
                obj.data.shape_keys.id_data.animation_data_create()

            if len(obj.data.shape_keys.id_data.animation_data.drivers) > 0:
                num_toggled_obj += 1
            for driver in obj.data.shape_keys.id_data.animation_data.drivers:
                if driver is not None:
                    num_toggled += 1
                    if self.action == "TOGGLE":
                        driver.mute = not driver.mute
                    if self.action == "MUTE":
                        driver.mute = True
                    if self.action == "UNMUTE":
                        driver.mute = False

        if self.action == "TOGGLE":
            action_word = "Toggled"
        elif self.action == "MUTE":
            action_word = "Muted"
        elif self.action == "UNMUTE":
            action_word = "Unmuted"

        self.report(
            {"INFO"},
            f"{action_word} {num_toggled} drivers for {num_toggled_obj} objects",
        )
        return {"FINISHED"}


classes = (
    SK_OT_apply_mods,
    SK_OT_bake_shapekey_animation,
    SK_OT_toggle_shapekeys_drivers,
)


def modifier_panel(self, context):
    layout = self.layout
    layout.separator()
    layout.operator("sk.apply_mods")


def animation_panel(self, context):
    layout = self.layout
    layout.separator()
    layout.operator("sk.bake_shapekey_animation")
    layout.operator("sk.toggle_shapekeys_drivers")


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.VIEW3D_MT_object_apply.append(modifier_panel)
    bpy.types.VIEW3D_MT_object_animation.append(animation_panel)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    bpy.types.VIEW3D_MT_object_apply.remove(modifier_panel)
    bpy.types.VIEW3D_MT_object_animation.remove(animation_panel)
